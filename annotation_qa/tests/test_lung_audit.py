import numpy as np

from lung_audit import build_row


AFFINE = np.diag([1.0, 1.0, 1.0, 1.0])
SPACING = (1.0, 1.0, 1.0)


def empty_masks(shape=(20, 20, 20)):
    return {name: np.zeros(shape, dtype=bool) for name in (
        "lung_left", "lung_right", "colon", "stomach", "liver",
        "kidney_left", "kidney_right")}


def test_lung_above_liver_and_empty_lung():
    masks = empty_masks()
    masks["liver"][8:10, 8:10, 8:10] = True
    masks["kidney_left"][8:10, 8:10, 4:6] = True
    masks["lung_left"][8:10, 8:10, 15:17] = True
    row = build_row("PanTS_00000001", masks, AFFINE, SPACING)
    assert row["lung_left_centroid_below_liver"] is False
    assert row["lung_left_centroid_below_kidney"] is False
    assert row["lung_left_z_min_mm"] == 15
    assert row["n_lungs_empty"] == 1
    assert row["lung_right_empty"] is True


def test_lung_inside_colon_reports_overlap_fractions():
    masks = empty_masks()
    masks["colon"][4:8, 5:9, 6:10] = True
    masks["lung_right"][4:8, 5:9, 6:10] = True
    row = build_row("PanTS_00000002", masks, AFFINE, SPACING)
    assert row["lung_right_overlap_colon_voxels"] == 64
    assert row["lung_right_overlap_colon_fraction_of_lung"] == 1.0
    assert row["lung_right_overlap_colon_fraction_of_colon"] == 1.0


def test_empty_lungs_have_zero_volume_and_no_centroid():
    row = build_row("PanTS_00000003", empty_masks(), AFFINE, SPACING)
    assert row["n_lungs_empty"] == 2
    assert row["lung_left_volume_ml"] == 0
    assert row["lung_left_centroid_z_mm"] is None
    assert row["lung_left_overlap_colon_fraction_of_lung"] == 0.0
