import os
import shutil
from pathlib import Path
from typing import Any
import pandas as pd

#from NiChart_DLMUSE import utils as utils
#from NiChart_DLMUSE import ReorientImage as reorient
#from NiChart_DLMUSE import SegmentImage as segimg
#from NiChart_DLMUSE import MaskImage as maskimg
#from NiChart_DLMUSE import RelabelROI as relabelimg
#from NiChart_DLMUSE import CalcROIVol as calcroi

import utils as utils
import ReorientImage as reorient
import SegmentImage as segimg
import MaskImage as maskimg
import RelabelROI as relabelroi
import CalcROIVol as calcroi

# Config vars
SUFF_LPS = '_LPS.nii.gz'
SUFF_DLICV = '_DLICV.nii.gz'
SUFF_DLMUSE = '_DLMUSE.nii.gz'
SUFF_ROI = '_DLMUSE_Volumes.csv'
OUT_CSV = 'DLMUSE_Volumes.csv'

REF_ORIENT = 'LPS'

# Dictionary for mapping consecutive dlmuse indices back to regular MUSE indices
DICT_MUSE_NNUNET_MAP = os.path.join(os.path.dirname(os.getcwd()), 
                                    'shared', 'dicts', 'MUSE_mapping_consecutive_indices.csv')
LABEL_FROM = "IndexConsecutive"
LABEL_TO = "IndexMUSE"

DICT_MUSE_SINGLE = DICT_MUSE_NNUNET_MAP
DICT_MUSE_DERIVED = os.path.join(os.path.dirname(os.getcwd()), 
                                 'shared', 'dicts', 'MUSE_mapping_derived_rois.csv')

def run_pipeline(in_data, out_dir, device):
    '''
    NiChart pipeline
    '''
    
    # Detect input images
    df_img = utils.make_img_list(in_data)

    # Set init paths and envs
    out_dir = os.path.abspath(out_dir)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    out_dir_final = out_dir        

    # Create working dir (FIXME: created within the output dir for now)
    working_dir = os.path.join(out_dir_final, "temp_working_dir")

    ## FIXME remove tmp out dir
    #if os.path.exists(working_dir):
        #shutil.rmtree(working_dir)

    os.makedirs(working_dir, exist_ok=True)

    ## Reorient image to LPS
    print('------------------------\n   Reorient images')
    out_dir = os.path.join(working_dir, "s1_reorient_lps")
    ref = REF_ORIENT
    out_suff = SUFF_LPS
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    reorient.apply_reorient_img(df_img, ref, out_dir, out_suff)

    ### Apply DLICV
    print('------------------------\n   Apply DLICV')
    in_dir = os.path.join(working_dir, "s1_reorient_lps")
    out_dir = os.path.join(working_dir, "s2_dlicv")
    in_suff = SUFF_LPS
    out_suff = SUFF_DLICV
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    segimg.run_dlicv(in_dir, in_suff, out_dir, out_suff, device)

    #input('next ...')

    ### Mask image
    print('------------------------\n   Apply DLICV mask')
    in_dir = os.path.join(working_dir, "s1_reorient_lps")
    mask_dir = os.path.join(working_dir, "s2_dlicv")
    out_dir = os.path.join(working_dir, "s3_masked")
    in_suff = SUFF_LPS
    mask_suff = SUFF_DLICV
    out_suff = SUFF_DLICV
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    maskimg.apply_mask_img(df_img, in_dir, in_suff, mask_dir, mask_suff, out_dir, out_suff)

    #input('next ...')

    ### Apply DLMUSE
    print('------------------------\n   Apply DLMUSE')
    in_dir = os.path.join(working_dir, "s3_masked")
    out_dir = os.path.join(working_dir, "s4_dlmuse")
    in_suff = SUFF_DLICV
    out_suff = SUFF_DLMUSE
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    segimg.run_dlmuse(in_dir, in_suff, out_dir, out_suff, device)

    #input('next ...')

    ### Relabel DLMUSE
    print('------------------------\n   Relabel DLMUSE')
    in_dir = os.path.join(working_dir, "s4_dlmuse")
    out_dir = os.path.join(working_dir, "s5_relabeled")
    in_suff = SUFF_DLMUSE
    out_suff = SUFF_DLMUSE
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    relabelroi.apply_relabel_rois(df_img, in_dir, in_suff, out_dir, out_suff, 
                                  DICT_MUSE_NNUNET_MAP, LABEL_FROM, LABEL_TO)

    #input('next ...')

    ### Combine DLICV and MUSE masks
    print('------------------------\n   Combine DLICV and DLMUSE masks')
    in_dir = os.path.join(working_dir, "s5_relabeled")
    mask_dir = os.path.join(working_dir, "s2_dlicv")
    out_dir = os.path.join(working_dir, "s6_combined")
    in_suff = SUFF_DLMUSE
    mask_suff = SUFF_DLICV
    out_suff = SUFF_DLMUSE
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    maskimg.apply_combine_masks(df_img, in_dir, in_suff, mask_dir, mask_suff, out_dir, out_suff)

    #input('next ...')

    ### Reorient to initial orientation
    print('------------------------\n   Reorient to initial')
    in_dir = os.path.join(working_dir, "s6_combined")
    out_dir = out_dir_final
    in_suff = SUFF_DLMUSE
    out_suff = SUFF_DLMUSE
    reorient.apply_reorient_to_init(df_img, in_dir, in_suff, out_dir, out_suff)

    #input('next ...')

    ### Create roi csv
    print('------------------------\n   Create csv')
    in_dir = out_dir_final
    out_dir = out_dir_final
    in_suff = SUFF_DLMUSE
    out_suff = SUFF_ROI
    calcroi.apply_create_roi_csv(df_img, in_dir, in_suff,
                                 DICT_MUSE_SINGLE, DICT_MUSE_DERIVED, 
                                 out_dir, out_suff)

    ### Combine roi csv
    print('------------------------\n   Combine csv')
    in_dir = out_dir_final
    out_dir = out_dir_final
    in_suff = SUFF_ROI
    out_name = OUT_CSV
    calcroi.combine_roi_csv(df_img, in_dir, in_suff, out_dir, out_name)

