import numpy as np

from component_sensitivity import component_metrics


SPACING = (1.0, 1.0, 1.0)


def test_corner_touch_connectivity():
    mask = np.zeros((8, 8, 8), dtype=bool)
    mask[2, 2, 2] = True
    mask[3, 3, 3] = True
    result = component_metrics(mask, SPACING)
    assert result["n_components_conn1"] == 2
    assert result["n_components_conn2"] == 2
    assert result["n_components_conn3"] == 1


def test_edge_touch_connectivity():
    mask = np.zeros((8, 8, 8), dtype=bool)
    mask[2, 2, 2] = True
    mask[3, 3, 2] = True
    result = component_metrics(mask, SPACING)
    assert result["n_components_conn1"] == 2
    assert result["n_components_conn2"] == 1
    assert result["n_components_conn3"] == 1


def test_big_blob_and_speck_reach_99_percent_in_one_component():
    mask = np.zeros((30, 30, 30), dtype=bool)
    mask[10:20, 10:20, 10:20] = True
    mask[1, 1, 1] = True
    mask[1, 1, 3] = True
    mask[1, 3, 1] = True
    result = component_metrics(mask, SPACING)
    assert result["n_components_conn3"] == 4
    assert result["n_for_99pct_volume_conn3"] == 1
