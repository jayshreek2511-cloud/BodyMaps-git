import nibabel as nib
import numpy as np

from dart_pilot_a import dice_coefficient, resample_mask_to_reference


def test_dice_and_nearest_neighbor_resampling():
    a = np.zeros((3, 3, 3), dtype=bool)
    b = np.zeros((3, 3, 3), dtype=bool)
    a[1, 1, 1] = True
    b[1, 1, 1] = True
    assert dice_coefficient(a, b) == 1.0
    assert dice_coefficient(a, np.zeros_like(a)) == 0.0
    assert dice_coefficient(np.zeros_like(a), np.zeros_like(a)) == 1.0

    source = np.zeros((2, 2, 2), dtype=np.uint8)
    source[0, 0, 0] = 1
    source_affine = np.eye(4)
    reference_affine = np.eye(4)
    reference_affine[:3, 3] = (0.25, 0.25, 0.25)
    reference = nib.Nifti1Image(np.zeros((3, 3, 3), dtype=np.uint8), reference_affine)

    aligned, changed = resample_mask_to_reference(source, source_affine, reference)
    assert changed
    assert aligned.shape == (3, 3, 3)
    assert aligned.any()
    assert aligned[0, 0, 0]
