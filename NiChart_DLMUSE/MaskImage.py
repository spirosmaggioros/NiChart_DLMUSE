import nibabel as nib
import numpy as np
from scipy import ndimage
from scipy.ndimage.measurements import label


def calc_bbox_with_padding(img: np.ndarray, perc_pad: int = 10) -> np.ndarray:
    """
    Finds bounding box for the foreground values in img, with a given padding percentage

    :param img: the passed image
    :type img: np.ndarray
    :param perc_pad: the given padding percentage
    :type perc_pad: int

    :return: an array with the coordinates of the bounding box
    :rtype: np.ndarray
    """

    img = img.astype("uint8")

    # Output is the coordinates of the bounding box
    bcoors = np.zeros([3, 2], dtype=int)

    # Find the largest connected component
    # INFO: In images with very large FOV DLICV may have small isolated regions in
    #       boundaries; so we calculate the bounding box based on the brain, not all
    #       foreground voxels
    str_3D = np.array(
        [
            [[0, 0, 0], [0, 1, 0], [0, 0, 0]],
            [[0, 1, 0], [1, 1, 1], [0, 1, 0]],
            [[0, 0, 0], [0, 1, 0], [0, 0, 0]],
        ],
        dtype="uint8",
    )
    labeled, ncomp = label(img, str_3D)
    sizes = ndimage.sum(img, labeled, range(ncomp + 1))
    img_largest_cc = (labeled == np.argmax(sizes)).astype(int)

    # Find coors in each axis
    for sel_axis in [0, 1, 2]:

        # Get axes other than the selected
        other_axes = [0, 1, 2]
        other_axes.remove(sel_axis)

        # Get img dim in selected axis
        dim = img_largest_cc.shape[sel_axis]

        # Find bounding box (index of first and last non-zero slices)
        nonzero = np.any(img_largest_cc, axis=tuple(other_axes))
        bbox = np.where(nonzero)[0][[0, -1]]

        # Add padding
        size_pad = int(np.round((bbox[1] - bbox[0]) * perc_pad / 100))
        b_min = int(np.max([0, bbox[0] - size_pad]))
        b_max = int(np.min([dim, bbox[1] + size_pad]))

        bcoors[sel_axis, :] = [b_min, b_max]

    return bcoors

def mask_img(in_img, mask_img, out_img):
    '''
    Applies the input mask to the input image
    Crops the image around the mask
    '''

    # Read input image and mask
    nii_in = nib.load(in_img)
    nii_mask = nib.load(mask_img)

    img_in = nii_in.get_fdata()
    img_mask = nii_mask.get_fdata()

    # Mask image
    img_in[img_mask == 0] = 0

    # INFO: nnunet hallucinated on images with large FOV. To solve this problem
    #       we added pre/post processing steps to crop initial image around ICV
    #       mask before sending to DLMUSE

    # Crop image
    bcoors = calc_bbox_with_padding(img_mask)
    img_in_crop = img_in[
        bcoors[0, 0] : bcoors[0, 1],
        bcoors[1, 0] : bcoors[1, 1],
        bcoors[2, 0] : bcoors[2, 1],
    ]

    # Save out image
    nii_out = nib.Nifti1Image(img_in_crop, nii_in.affine, nii_in.header)
    nii_out.to_filename(out_img)

def combine_masks(in_img, icv_img, out_img):
    ''''
    Combine icv and muse masks
    '''

    # Read input images
    nii_in = nib.load(in_img)
    nii_icv = nib.load(icv_img)

    img_in = nii_in.get_fdata()
    img_icv = nii_icv.get_fdata()

    # INFO: nnunet hallucinated on images with large FOV. To solve this problem
    #       we added pre/post processing steps to crop initial image around ICV
    #       mask before sending to DLMUSE
    #
    # MUSE image (img_in) may be cropped. Pad it to initial image size
    bcoors = calc_bbox_with_padding(img_icv)
    img_out = img_icv * 0
    img_out[
        bcoors[0, 0] : bcoors[0, 1],
        bcoors[1, 0] : bcoors[1, 1],
        bcoors[2, 0] : bcoors[2, 1],
    ] = img_in

    # Merge masks : Add a new label (1) to MUSE for foreground voxels in ICV that is not in MUSE
    # this label will mainly represent cortical CSF
    img_out[(img_out == 0) & (img_icv > 0)] = 1

    img_out = img_out.astype(int)

    # Save out image
    nii_out = nib.Nifti1Image(img_out, nii_in.affine, nii_in.header)
    nii_out.to_filename(out_img)


def apply_mask_img(df_img, in_dir, mask_dir, out_dir,
                   in_suff = '_LPS.nii.gz',
                   mask_suffix = '_LPS.nii.gz',
                   out_suffix = '_LPS.nii.gz'):
    '''
    Apply reorientation to all images
    '''
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    for i, tmp_row in df_img.iterrows():
        img_prefix = tmp_row.MRID
        in_img = os.path.join(in_dir, img_prefix + in_suffix)
        mask_img = os.path.join(mask_dir, img_prefix + mask_suffix)
        out_img = os.path.join(out_dir, img_prefix + out_suffix)

        mask_img(in_img, mask_img, out_img)

def apply_combine_masks(df_img, dlmuse_dir, dlicv_dir, out_dir,
                        dlmuse_suff = '_LPS.nii.gz',
                        dlicv_suffix = '_LPS.nii.gz',
                        out_suffix = '_LPS.nii.gz'):
    '''
    Apply reorientation to all images
    '''
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    for i, tmp_row in df_img.iterrows():
        img_prefix = tmp_row.MRID
        dlmuse_mask = os.path.join(in_dir, img_prefix + in_suffix)
        dlicv_mask = os.path.join(mask_dir, img_prefix + mask_suffix)
        out_img = os.path.join(out_dir, img_prefix + out_suffix)

        combine_masks(in_img, icv_img, out_img)
