import numpy as np

from component_features import component_features


def test_component_distances_use_physical_spacing_and_small_components():
    mask = np.zeros((80, 40, 40), dtype=bool)
    mask[10:20, 10:20, 10:20] = True  # 1 mL main component at 1 mm spacing
    mask[24, 15:17, 15] = True
    mask[24, 15, 16] = True  # three voxels, 5 mm from the main component
    mask[59, 15:17, 15] = True
    mask[59, 15, 16] = True  # three voxels, 40 mm from the main component

    result = component_features(mask, (1.0, 1.0, 1.0))

    assert result["n_components_all"] == 3
    assert result["n_ge_0p1ml"] == 1
    assert result["n_ge_1ml"] == 1
    assert result["n_for_99pct_volume"] == 1
    assert result["n_small_far_gt_10mm"] == 1
    assert result["n_small_far_gt_30mm"] == 1
    # The two small components are exactly 5 mm and 40 mm from the large one;
    # allow one 1 mm voxel of tolerance.
    assert abs(result["small_dist_median_mm"] - 22.5) <= 1.0
    assert abs(result["small_dist_max_mm"] - 40.0) <= 1.0
    assert abs(result["small_dist_to_nearest_large_median_mm"] - 22.5) <= 1.0
    assert abs(result["small_dist_to_nearest_large_max_mm"] - 40.0) <= 1.0
    assert np.isclose(result["small_volume_far_gt_10mm_fraction"], 3 / 1006)
    for distance, x in ((5.0, 24), (40.0, 59)):
        single_speck = np.zeros_like(mask)
        single_speck[10:20, 10:20, 10:20] = True
        single_speck[x, 15:17, 15] = True
        single_speck[x, 15, 16] = True
        measured = component_features(single_speck, (1.0, 1.0, 1.0))
        assert abs(measured["small_dist_max_mm"] - distance) <= 1.0


def test_anisotropic_distance_uses_array_axis_spacing_order():
    mask = np.zeros((40, 40, 40), dtype=bool)
    mask[10:30, 10:30, 10:14] = True  # 1.2 mL at 0.5 x 0.5 x 3 mm
    mask[20, 20, 17:20] = True  # nearest z-face is 4 slices = 12 mm away
    result = component_features(mask, (0.5, 0.5, 3.0))
    assert result["n_components_all"] == 2
    assert abs(result["small_dist_median_mm"] - 12.0) <= 3.0
    assert abs(result["small_dist_to_nearest_large_max_mm"] - 12.0) <= 3.0
    # Reversing the sampling tuple would give 2 mm, outside the 3 mm tolerance.
    assert abs(result["small_dist_to_nearest_large_max_mm"] - 2.0) > 3.0


def test_nearest_large_uses_all_large_components_not_just_largest():
    mask = np.zeros((120, 40, 40), dtype=bool)
    mask[5:20, 10:20, 10:20] = True  # largest, 1.5 mL
    mask[70:80, 10:20, 10:20] = True  # second large component, 1 mL
    mask[82, 15:17, 15] = True
    mask[82, 15, 16] = True  # 3-voxel speck, 3 mm from the second blob

    result = component_features(mask, (1.0, 1.0, 1.0))

    assert result["n_ge_1ml"] == 2
    assert result["small_dist_max_mm"] > 60.0
    assert result["small_dist_to_nearest_large_max_mm"] == 3.0
    assert result["n_small_far_from_all_large_gt_10mm"] == 0
    assert result["n_small_far_from_all_large_gt_30mm"] == 0


def test_no_small_components_have_zero_nearest_large_distances():
    mask = np.ones((10, 10, 10), dtype=bool)
    result = component_features(mask, (1.0, 1.0, 1.0))
    assert result["small_dist_to_nearest_large_median_mm"] == 0.0
    assert result["small_dist_to_nearest_large_max_mm"] == 0.0
