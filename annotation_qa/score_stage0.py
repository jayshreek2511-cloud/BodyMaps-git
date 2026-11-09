"""Add per-organ Stage 0 anomaly scores and heuristic guesses."""
import argparse
import csv
from pathlib import Path
import numpy as np
from sklearn.ensemble import IsolationForest
from config import (ISOLATION_CONTAMINATION, ISOLATION_RANDOM_STATE,
                    ISOLATION_TOP_FRACTION, MAX_VOLUME_ML, MIN_COHORT_CASES,
                    MIN_VOLUME_ML, PERCENTILE_ANOMALY, LUNG_LABEL_IDS,
                    LUNG_OVERLAP_HIGH, LUNG_OVERLAP_LOW)

NON_FEATURES = {"case_id", "organ", "label_id", "technical_error",
 "left_right_side", "a", "z", "a_triggered", "z_triggered",
 "technical_error_triggered", "guessed_error_types", "n_triggered", "stage0_status",
 "lung_overlap_fraction", "lung_overlap_flag", "label_ids_present"}


def _is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def numeric_features(rows):
    """Return numeric model inputs, excluding categorical/comma-separated columns."""
    if not rows:
        return []
    features = []
    for key in rows[0]:
        if key in NON_FEATURES:
            continue
        values = [row.get(key, "") for row in rows]
        if any(isinstance(value, str) and "," in value for value in values):
            continue
        if any(_is_number(value) for value in values):
            features.append(key)
    return features

def percentile(values):
    values = np.asarray(values, float)
    if len(values) < 2:
        return np.zeros(len(values))
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), float)
    ranks[order] = np.arange(len(values))
    return ranks / (len(values) - 1)


def guesses(row, organ):
    result = []
    if int(float(row.get("n_small_fragments") or 0)) > 0:
        result.append("fragmentation (guess)")
    if str(row.get("any_edge_touch", "")).lower() in ("true", "1"):
        result.append("truncation (guess)")
    c = float(row.get("compactness") or 0)
    if c > 50 or (0 < c < 0.02):
        result.append("shape_anomaly (guess)")
    v = float(row.get("volume_ml") or 0)
    if 0 < v < MIN_VOLUME_ML:
        result.append("missing_region (guess)")
    if v > MAX_VOLUME_ML[organ] or float(row.get("contact_other_pair_organ_fraction") or 0) > 0.25:
        result.append("leakage (guess)")
    return result


def apply_lung_overlap_rule(row):
    """Add a data-independent lung overlap flag and its anatomical guess."""
    overlap = 0.0
    for slot in (1, 2):
        try:
            label = int(float(row.get(f"overlap_top{slot}_label") or 0))
            fraction = float(row.get(f"overlap_top{slot}_fraction") or 0)
        except (TypeError, ValueError):
            continue
        if label in LUNG_LABEL_IDS:
            overlap += fraction
    row["lung_overlap_fraction"] = overlap
    if overlap > LUNG_OVERLAP_HIGH:
        flag = "high"
    elif overlap > LUNG_OVERLAP_LOW:
        flag = "low"
    else:
        flag = "none"
    row["lung_overlap_flag"] = flag
    if flag == "high":
        if row.get("stage0_status") != "technical_error":
            row["stage0_status"] = "suspicious"
        guesses = [g for g in str(row.get("guessed_error_types", "")).split("; ") if g]
        if "leakage_into_lung (rule)" not in guesses:
            guesses.append("leakage_into_lung (rule)")
        row["guessed_error_types"] = "; ".join(guesses)
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", default="features.csv")
    p.add_argument("--out", default="scored.csv")
    a = p.parse_args()
    with Path(a.input).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        p.error("input CSV has no data rows")
    reliable = len({r["case_id"] for r in rows}) >= MIN_COHORT_CASES
    if not reliable:
        print(f"WARNING: fewer than {MIN_COHORT_CASES} cases; thresholds are not reliable. Percentile cutoffs skipped; raw scores written.")
    numeric = numeric_features(rows)
    scored = []
    for organ in sorted({r["organ"] for r in rows}):
        indices = [i for i, r in enumerate(rows) if r["organ"] == organ]
        x = np.array([[float(rows[i].get(k) or 0) for k in numeric] for i in indices])
        if x.shape[1] == 0:
            x = np.zeros((len(indices), 1))
        median = np.median(x, axis=0)
        mad = np.median(np.abs(x - median), axis=0)
        scale = np.where(mad > 0, mad, 1e-12)
        rz = 0.6745 * (x - median) / scale
        combined = np.mean(np.sort(np.abs(rz), axis=1)[:, -min(5, rz.shape[1]):], axis=1)
        if len(indices) >= 2:
            model = IsolationForest(contamination=ISOLATION_CONTAMINATION,
                       random_state=ISOLATION_RANDOM_STATE, n_estimators=200)
            model.fit(x)
            iso = -model.decision_function(x)
        else:
            iso = np.zeros(len(indices))
        aa = percentile(combined) if reliable else combined
        zz = percentile(iso) if reliable else iso
        for j, index in enumerate(indices):
            row = dict(rows[index])
            row["a"], row["z"] = float(aa[j]), float(zz[j])
            tech = bool(row.get("technical_error", "").strip())
            row["a_triggered"] = bool(reliable and aa[j] >= PERCENTILE_ANOMALY)
            row["z_triggered"] = bool(reliable and zz[j] >= 1 - ISOLATION_TOP_FRACTION)
            row["technical_error_triggered"] = tech
            row["guessed_error_types"] = "; ".join(guesses(row, organ))
            row["n_triggered"] = int(row["a_triggered"]) + int(row["z_triggered"]) + int(tech)
            row["stage0_status"] = "technical_error" if tech else ("suspicious" if row["n_triggered"] else "provisional_ok")
            apply_lung_overlap_rule(row)
            scored.append(row)
    fields = list(dict.fromkeys([*rows[0], "lung_overlap_fraction", "lung_overlap_flag", "a", "z", "a_triggered", "z_triggered",
       "technical_error_triggered", "guessed_error_types", "n_triggered", "stage0_status"]))
    with Path(a.out).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(scored)
    print(f"Wrote {len(scored)} rows to {a.out}")


if __name__ == "__main__":
    main()
