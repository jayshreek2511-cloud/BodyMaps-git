"""Hard technical screening rules."""
from config import MAX_COMPONENTS, MAX_VOLUME_ML, MIN_VOLUME_ML


def technical_error(features, organ, file_error=None, missing_organ_file=False):
    """Return one or more hard technical reasons, or an empty string."""
    if missing_organ_file:
        return "missing_organ_file"
    if file_error:
        return f"file_unreadable: {file_error}"
    if not features or float(features.get("volume_ml", 0)) <= 0:
        return "empty_mask"
    reasons = []
    volume = float(features["volume_ml"])
    if volume < MIN_VOLUME_ML:
        reasons.append(f"volume_below_{MIN_VOLUME_ML:g}ml")
    if volume > MAX_VOLUME_ML[organ]:
        reasons.append(f"volume_above_{MAX_VOLUME_ML[organ]:g}ml")
    if features.get("n_components", 0) > MAX_COMPONENTS[organ]:
        reasons.append(f"too_many_components: {features['n_components']}")
    return "; ".join(reasons)
