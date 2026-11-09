"""Published PanTS ids and fixed Stage 0 screening defaults."""
LABEL_IDS = {
    "background": 0, "aorta": 3, "bladder": 4, "colon": 6, "duodenum": 8,
    "femur_left": 9, "femur_right": 10, "kidney_left": 12, "kidney_right": 13,
    "liver": 14, "lung_left": 15, "lung_right": 16, "pancreas": 17,
    "spleen": 24, "stomach": 25,
}
ORGANS_TO_EVALUATE = ["stomach", "colon"]
MIN_VOLUME_ML = 5.0
MAX_VOLUME_ML = {"stomach": 2500.0, "colon": 4000.0}
MAX_COMPONENTS = {"stomach": 10, "colon": 20}
SMALL_FRAGMENT_ML = 1.0
EXTREME_BBOX_MM = {"stomach": 400.0, "colon": 600.0}
PERCENTILE_ANOMALY = 0.98
ISOLATION_TOP_FRACTION = 0.03
ISOLATION_CONTAMINATION = 0.03
ISOLATION_RANDOM_STATE = 17
MIN_COHORT_CASES = 30
# Provisional anatomical thresholds; not tuned on data.
LUNG_LABEL_IDS = [15, 16]
LUNG_OVERLAP_HIGH = 0.01
LUNG_OVERLAP_LOW = 0.0005
