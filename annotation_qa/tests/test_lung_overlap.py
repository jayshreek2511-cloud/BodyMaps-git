from score_stage0 import apply_lung_overlap_rule


def row(top1_label=15, top1_fraction=0.0, top2_label=0, top2_fraction=0.0):
    return {
        "overlap_top1_label": top1_label,
        "overlap_top1_fraction": top1_fraction,
        "overlap_top2_label": top2_label,
        "overlap_top2_fraction": top2_fraction,
        "stage0_status": "provisional_ok",
        "guessed_error_types": "",
    }


def test_high_lung_overlap_sets_rule_guess_without_cohort():
    scored = apply_lung_overlap_rule(row(top1_fraction=0.6))
    assert scored["lung_overlap_fraction"] == 0.6
    assert scored["lung_overlap_flag"] == "high"
    assert scored["stage0_status"] == "suspicious"
    assert scored["guessed_error_types"] == "leakage_into_lung (rule)"


def test_tiny_overlap_is_none():
    scored = apply_lung_overlap_rule(row(top1_label=15, top1_fraction=0.0001))
    assert scored["lung_overlap_flag"] == "none"


def test_lung_label_in_second_slot_counts():
    scored = apply_lung_overlap_rule(
        row(top1_label=8, top1_fraction=0.002,
            top2_label=15, top2_fraction=0.02)
    )
    assert scored["lung_overlap_fraction"] == 0.02
    assert scored["lung_overlap_flag"] == "high"


def test_intermediate_overlap_is_low():
    scored = apply_lung_overlap_rule(row(top1_label=16, top1_fraction=0.001))
    assert scored["lung_overlap_flag"] == "low"
