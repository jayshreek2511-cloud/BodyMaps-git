import numpy as np
from config import LABEL_IDS
from features import extract_features
from checks import technical_error

SPACING = (1.0, 1.0, 1.0)


def feat(volume, label=LABEL_IDS["stomach"], organ_mask=None):
    return extract_features(volume, label, SPACING, volume, organ_mask=organ_mask)


def test_clean_blob():
    v = np.zeros((32, 32, 32), dtype=np.uint8)
    v[10:22, 10:22, 10:22] = LABEL_IDS["stomach"]
    f = feat(v)
    assert f["volume_ml"] == 1.728
    assert f["n_components"] == 1
    assert f["largest_component_fraction"] == 1.0
    assert (f["bbox_x_mm"], f["bbox_y_mm"], f["bbox_z_mm"]) == (12, 12, 12)
    assert not f["any_edge_touch"]
    assert f["contact_background_fraction"] == 1.0
    assert f["surface_area_mm2"] > 0
    assert f["overlap_other_labels_fraction"] == 0.0
    assert f["combined_vs_separate_ratio"] == 1.0


def test_overlap_top1_uses_only_mask_voxels():
    combined = np.zeros((12, 12, 12), dtype=np.uint8)
    combined[2:9, 2:9, 2:9] = 7
    mask = np.zeros_like(combined, dtype=bool)
    mask[4:6, 4:9, 4] = True
    combined[mask] = LABEL_IDS["stomach"]
    points = np.argwhere(mask)
    for point in points[:5]:
        combined[tuple(point)] = 8
    f = extract_features(combined, LABEL_IDS["stomach"], SPACING,
                         combined, organ_mask=mask)
    assert int(mask.sum()) == 10
    assert f["overlap_top1_label"] == 8
    assert f["overlap_top1_fraction"] == 0.5


def test_separate_small_fragment():
    v = np.zeros((32, 32, 32), dtype=np.uint8)
    v[10:22, 10:22, 10:22] = LABEL_IDS["stomach"]
    v[25, 25, 25] = LABEL_IDS["stomach"]
    f = feat(v)
    assert f["n_components"] == 2
    assert f["n_small_fragments"] == 1
    assert f["fragment_volume_fraction"] == 1 / 1729
    assert technical_error(f, "stomach") == "volume_below_5ml"


def test_scan_edge_is_feature_only():
    v = np.zeros((20, 20, 20), dtype=np.uint8)
    v[0:4, 8:12, 8:12] = LABEL_IDS["colon"]
    f = feat(v, LABEL_IDS["colon"])
    assert f["touches_scan_edge_x_min"] and f["any_edge_touch"]
    assert "touches_scan_edge" not in technical_error(f, "colon")
    assert "volume_below_5ml" in technical_error(f, "colon")


def test_missing_organ_file_error():
    assert technical_error({}, "stomach", missing_organ_file=True) == "missing_organ_file"


def test_empty():
    f = feat(np.zeros((12, 12, 12), dtype=np.uint8))
    assert f["volume_ml"] == 0 and f["n_components"] == 0
    assert technical_error(f, "stomach") == "empty_mask"
