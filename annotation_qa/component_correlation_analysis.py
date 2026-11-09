"""Spearman correlation and redundancy analysis for component features."""
import argparse
import csv
from pathlib import Path
import tempfile
import time
import warnings

import numpy as np
from scipy.stats import spearmanr

FEATURES = (
    "n_components_all",
    "n_ge_1ml",
    "n_for_99pct_volume",
    "small_volume_fraction_1ml",
    "largest_component_fraction",
    "small_dist_to_nearest_large_median_mm",
    "small_dist_to_nearest_large_max_mm",
    "n_small_far_from_all_large_gt_10mm",
    "n_small_far_from_all_large_gt_30mm",
)
ORGANS = ("colon", "stomach")
BINS = ("<=1", "1-3", "3-5", ">5")
OUT_NAMES = (
    "component_feature_spearman_rho.csv",
    "component_feature_spearman_pvalues.csv",
    "component_feature_correlation_summary.txt",
)


def snapshot_csv(source, destination):
    source = Path(source)
    before = source.stat()
    time.sleep(1.0)
    stable = source.stat()
    if (before.st_size, before.st_mtime_ns) != (stable.st_size, stable.st_mtime_ns):
        raise RuntimeError(f"Input CSV changed before copy: {source}")
    destination = Path(destination)
    with source.open("rb") as src, destination.open("xb") as dst:
        while True:
            block = src.read(1024 * 1024)
            if not block:
                break
            dst.write(block)
    after = source.stat()
    if (stable.st_size, stable.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Input CSV changed during copy: {source}")
    return destination


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def number(row, column):
    try:
        return float(row.get(column, ""))
    except (TypeError, ValueError):
        return float("nan")


def thickness_bin(spacing_z):
    value = round(float(spacing_z), 3)
    if value <= 1:
        return "<=1"
    if value <= 3:
        return "1-3"
    if value <= 5:
        return "3-5"
    return ">5"


def load_joined(feature_rows, score_rows):
    def key(row):
        return row.get("case_id", ""), row.get("organ", "")

    for name, rows in (("component features", feature_rows), ("scored", score_rows)):
        keys = [key(row) for row in rows]
        duplicates = len(keys) - len(set(keys))
        if duplicates:
            raise ValueError(f"{name} has {duplicates} duplicate (case_id, organ) keys")
    score_map = {key(row): row for row in score_rows}
    missing = []
    empty_by_organ = {organ: 0 for organ in ORGANS}
    error_by_organ = {organ: 0 for organ in ORGANS}
    valid = []
    for feature in feature_rows:
        case_key = key(feature)
        score = score_map.get(case_key)
        if score is None:
            missing.append(case_key)
            continue
        organ = feature.get("organ", "")
        f_error = (feature.get("error") or "").strip().lower()
        s_error = (score.get("technical_error") or "").strip().lower()
        is_empty = (
            f_error == "empty_mask" or s_error == "empty_mask"
            or number(feature, "n_components_all") == 0
        )
        if is_empty:
            if organ in empty_by_organ:
                empty_by_organ[organ] += 1
            continue
        if f_error or "unreadable" in s_error or "missing" in s_error:
            if organ in error_by_organ:
                error_by_organ[organ] += 1
            continue
        if organ not in ORGANS:
            continue
        row = dict(feature)
        row["spacing_z"] = round(number(score, "spacing_z"), 3)
        row["thickness_bin"] = thickness_bin(row["spacing_z"])
        valid.append(row)
    return valid, missing, empty_by_organ, error_by_organ


def matrix_for(rows):
    data = np.asarray([[number(row, feature) for feature in FEATURES] for row in rows], dtype=float)
    if data.size == 0:
        data = np.empty((0, len(FEATURES)), dtype=float)
    keep = np.isfinite(data).all(axis=1)
    data = data[keep]
    n = len(data)
    rho = np.full((len(FEATURES), len(FEATURES)), np.nan, dtype=float)
    pvalue = np.full_like(rho, np.nan)
    if n >= 3:
        for i in range(len(FEATURES)):
            if np.unique(data[:, i]).size < 2:
                continue
            rho[i, i] = 1.0
            pvalue[i, i] = 0.0
            for j in range(i + 1, len(FEATURES)):
                if np.unique(data[:, j]).size < 2:
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    result = spearmanr(data[:, i], data[:, j])
                rho[i, j] = rho[j, i] = float(result.statistic)
                pvalue[i, j] = pvalue[j, i] = float(result.pvalue)
    return n, rho, pvalue


def write_matrix(path, matrices, value_name):
    header = ["organ", "thickness_bin", "n_valid", "feature", *FEATURES]
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        for organ, bin_name, n, matrix in matrices:
            for index, feature in enumerate(FEATURES):
                vals = ["" if not np.isfinite(x) else f"{x:.12g}" for x in matrix[index]]
                writer.writerow([organ, bin_name, n, feature, *vals])


def analyze(valid_rows):
    matrices = []
    group_counts = {}
    high_pairs = []
    for organ in ORGANS:
        organ_rows = [r for r in valid_rows if r["organ"] == organ]
        groups = [("overall", organ_rows)]
        groups.extend((name, [r for r in organ_rows if r["thickness_bin"] == name]) for name in BINS)
        for bin_name, rows in groups:
            n, rho, pvalue = matrix_for(rows)
            group_counts[(organ, bin_name)] = (len(rows), n)
            matrices.append((organ, bin_name, n, rho, pvalue))
            for i in range(len(FEATURES)):
                for j in range(i + 1, len(FEATURES)):
                    value = rho[i, j]
                    if np.isfinite(value) and abs(value) >= 0.90:
                        high_pairs.append((organ, bin_name, FEATURES[i], FEATURES[j], value, pvalue[i, j], n))
    return matrices, group_counts, high_pairs


def redundancy_check(valid_rows):
    result = {}
    for organ in ORGANS:
        rows = [r for r in valid_rows if r["organ"] == organ]
        cells = {(False, False): 0, (False, True): 0, (True, False): 0, (True, True): 0}
        # n_for_99pct_volume == 1 iff the largest component alone covers at least 99%.
        violations = []
        for row in rows:
            n99_is_one = number(row, "n_for_99pct_volume") == 1
            largest_at_least_99 = number(row, "largest_component_fraction") >= 0.99
            cells[(n99_is_one, largest_at_least_99)] += 1
            if n99_is_one != largest_at_least_99:
                violations.append(row.get("case_id", ""))
        result[organ] = (len(rows), cells, violations)
    return result


def build_summary(feature_rows, score_rows, valid, missing, empty_by_organ, errors_by_organ,
                  group_counts, high_pairs, redundancy):
    lines = [
        "Component feature Spearman correlation and redundancy summary",
        "Threshold note: |rho| >= 0.90 is the requested flag for potentially redundant pairs; it does not mean a feature is useless.",
        "No new extraction thresholds were introduced. Slice bins use spacing_z rounded to 3 decimals: <=1, (1,3], (3,5], >5 mm.",
        f"Input rows: component_features={len(feature_rows)}, scored={len(score_rows)}.",
        f"Join key: (case_id, organ); unmatched component rows={len(missing)}; duplicate keys checked and absent.",
        f"Empty masks excluded: colon={empty_by_organ['colon']}, stomach={empty_by_organ['stomach']}, total={sum(empty_by_organ.values())}.",
        f"Other unreadable/missing/error rows excluded: colon={errors_by_organ['colon']}, stomach={errors_by_organ['stomach']}.",
        f"Valid joined rows: colon={sum(r['organ']=='colon' for r in valid)}, stomach={sum(r['organ']=='stomach' for r in valid)}.",
        "",
        "Valid matrix sample sizes (listwise complete across all 9 requested features):",
    ]
    for organ in ORGANS:
        for group in ("overall", *BINS):
            rows_n, matrix_n = group_counts[(organ, group)]
            lines.append(f"  {organ} / {group}: valid rows={rows_n}; matrix n={matrix_n}")
    lines.extend(["", "Potentially redundant pairs with |rho| >= 0.90 (Spearman; reported by organ/group):"])
    if high_pairs:
        for organ, group, left, right, rho, pvalue, n in high_pairs:
            lines.append(f"  {organ} / {group}: {left} vs {right}: rho={rho:.6f}, p={pvalue:.6g}, n={n} (potentially redundant, not automatically useless)")
    else:
        lines.append("  None")
    lines.extend([
        "",
        "Mathematical relationship check: implementation computes n_for_99pct_volume as the smallest number of largest components whose cumulative voxel count reaches 99% of total; largest_component_fraction is the largest component's voxel count divided by total.",
        "Therefore n_for_99pct_volume == 1 iff largest_component_fraction >= 0.99; the values are related but n_for_99pct_volume can take values above 1 and is not generally determined by largest_component_fraction alone.",
        "Actual-data cross-tab (rows n_for_99pct_volume == 1; columns largest_component_fraction >= 0.99):",
    ])
    for organ in ORGANS:
        n, cells, violations = redundancy[organ]
        lines.append(f"  {organ}: valid n={n}; both true={cells[(True,True)]}; n99-only={cells[(True,False)]}; fraction-only={cells[(False,True)]}; both false={cells[(False,False)]}; equivalence violations={len(violations)}")
        if violations:
            lines.append("    violating case IDs: " + ", ".join(violations[:30]))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-features", default=r"D:\PanTS_data\component_features_all.csv")
    parser.add_argument("--scored", default=r"D:\PanTS_data\scored_all.csv")
    parser.add_argument("--out-dir", default=r"D:\PanTS_data\component_study")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_paths = [out_dir / name for name in OUT_NAMES]
    existing = [str(path) for path in out_paths if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite correlation outputs: " + ", ".join(existing))
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".component_correlation_snapshot_", dir=Path(__file__).parent) as td:
        td = Path(td)
        fc = snapshot_csv(args.component_features, td / "component_features.csv")
        sc = snapshot_csv(args.scored, td / "scored.csv")
        feature_rows, score_rows = read_csv(fc), read_csv(sc)
    valid, missing, empty_by_organ, errors_by_organ = load_joined(feature_rows, score_rows)
    if missing:
        raise ValueError(f"Join validation failed: {len(missing)} component rows have no score row; examples={missing[:10]}")
    matrices, group_counts, high_pairs = analyze(valid)
    rho_matrices = [(o, b, n, rho) for o, b, n, rho, _ in matrices]
    p_matrices = [(o, b, n, p) for o, b, n, _, p in matrices]
    write_matrix(out_paths[0], rho_matrices, "rho")
    write_matrix(out_paths[1], p_matrices, "pvalue")
    redundancy = redundancy_check(valid)
    summary = build_summary(feature_rows, score_rows, valid, missing, empty_by_organ, errors_by_organ,
                            group_counts, high_pairs, redundancy)
    with out_paths[2].open("x", encoding="utf-8", newline="") as stream:
        stream.write(summary)
    print(summary)
    print("Saved outputs:")
    for path in out_paths:
        print(f"  {path}")
    print(f"Correlation matrices saved with feature rows and columns: {', '.join(FEATURES)}")


if __name__ == "__main__":
    main()
