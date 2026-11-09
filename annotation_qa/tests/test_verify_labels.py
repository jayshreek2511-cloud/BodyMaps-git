import math

from verify_labels import group_for, relative_difference


def test_relative_difference_uses_combined_as_reference():
    assert relative_difference(102, 100) == 2.0
    assert relative_difference(90, 100) == 10.0
    assert relative_difference(0, 0) == 0.0
    assert math.isinf(relative_difference(1, 0))


def test_groups_by_worst_organ_difference():
    assert group_for({"stomach": (1, 1, 1.99), "colon": (1, 1, 0.0)}) == "<2% (ok)"
    assert group_for({"stomach": (1, 1, 2.0), "colon": (1, 1, 0.0)}) == "2-5%"
    assert group_for({"stomach": (1, 1, 5.0), "colon": (1, 1, 0.0)}) == "2-5%"
    assert group_for({"stomach": (1, 1, 0.0), "colon": (1, 1, 5.01)}) == ">5%"
