"""Summarize component features joined to Stage 0 colon/stomach rows."""
import argparse
import csv
from pathlib import Path
import shutil
import tempfile
import time

import numpy as np

THICKNESS_BINS = ("<=1", "1-3", "3-5", ">5")
METRICS = (
    "n_components_all", "n_ge_1ml", "n_for_99pct_volume",
    "small_volume_fraction_1ml", "largest_component_fraction",
    "small_dist_to_nearest_large_max_mm",
)
PERCENTILES = (50, 90, 95, 99)


def snapshot_csv(source, destination):
    """Copy a stable CSV, then let the caller read only the snapshot."""
    source = Path(source)
    before = source.stat()
    time.sleep(1.0)
    stable = source.stat()
    if (before.st_size, before.st_mtime_ns) != (stable.st_size, stable.st_mtime_ns):
        raise RuntimeError(f"CSV changed before snapshot; refusing to read it: {source}")
    shutil.copyfile(source, destination)
    after = source.stat()
    if (stable.st_size, stable.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        Path(destination).unlink(missing_ok=True)
        raise RuntimeError(f"CSV changed during snapshot; refusing to read it: {source}")
    return Path(destination)


def thickness_bin(value):
    z = round(float(value), 3)
    if z <= 1:
        return "<=1"
    if z <= 3:
        return "1-3"
    if z <= 5:
        return "3-5"
    return ">5"


def numeric(row, key):
    try:
        return float(row.get(key, ""))
    except (TypeError, ValueError):
        return float("nan")


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def summarize(features_rows, scored_rows):
    scored = {(r.get("case_id", ""), r.get("organ", "")): r
              for r in scored_rows}
    matched = []
    missing_score = 0
    empty_rows = 0
    other_error_rows = 0
    for feature in features_rows:
        key = (feature.get("case_id", ""), feature.get("organ", ""))
        score = scored.get(key)
        if score is None:
            missing_score += 1
            continue
        ferr = (feature.get("error") or "").strip().lower()
        terr = (score.get("technical_error") or "").strip().lower()
        if ferr == "empty_mask" or terr == "empty_mask" or numeric(feature, "n_components_all") == 0:
            empty_rows += 1
            continue
        if ferr or "unreadable" in terr or "missing" in terr:
            other_error_rows += 1
            continue
        row = dict(feature)
        row["spacing_z"] = round(numeric(score, "spacing_z"), 3)
        row["thickness_bin"] = thickness_bin(score["spacing_z"])
        row["scored_n_components_26"] = numeric(score, "n_components")
        row["technical_error"] = score.get("technical_error", "")
        matched.append(row)
    return matched, missing_score, empty_rows, other_error_rows


def fmt_percentile(rows, metric, percentile):
    values = np.asarray([numeric(row, metric) for row in rows], dtype=float)
    values = values[np.isfinite(values)]
    return f"{np.percentile(values, percentile):.6g}" if len(values) else "NA"


def count_rule(rows, predicate):
    count = sum(bool(predicate(row)) for row in rows)
    pct = 100.0 * count / len(rows) if rows else 0.0
    return count, pct


def print_summary(rows):
    print("PROVISIONAL, NOT VALIDATED: every cutoff below is an exploratory reporting rule.")
    print("Cutoffs: components >20; n_ge_1ml >1 or >3; n_for_99pct_volume >1; "
          "largest fraction <0.8; far-small counts >=1 or >=5; distance >10 or >30 mm.")
    print("Percentile values are descriptive; percentages use non-empty joined rows.")
    print(f"Valid joined rows: {len(rows)}")
    rules = [
        ("old_rule_n_components_all_gt_20", lambda r: numeric(r, "n_components_all") > 20),
        ("n_ge_1ml_gt_1", lambda r: numeric(r, "n_ge_1ml") > 1),
        ("n_ge_1ml_gt_3", lambda r: numeric(r, "n_ge_1ml") > 3),
        ("n_for_99pct_volume_gt_1", lambda r: numeric(r, "n_for_99pct_volume") > 1),
        ("largest_component_fraction_lt_0.8", lambda r: numeric(r, "largest_component_fraction") < 0.8),
        ("n_small_far_gt_10mm_ge_1", lambda r: numeric(r, "n_small_far_from_all_large_gt_10mm") >= 1),
        ("n_small_far_gt_10mm_ge_5", lambda r: numeric(r, "n_small_far_from_all_large_gt_10mm") >= 5),
        ("n_small_far_gt_30mm_ge_1", lambda r: numeric(r, "n_small_far_from_all_large_gt_30mm") >= 1),
    ]
    for organ in ("colon", "stomach"):
        organ_rows = [r for r in rows if r.get("organ") == organ]
        print(f"\nORGAN: {organ} (n={len(organ_rows)})")
        for bin_name in THICKNESS_BINS:
            group = [r for r in organ_rows if r["thickness_bin"] == bin_name]
            print(f"  Slice-thickness {bin_name} mm (n={len(group)}):")
            for metric in METRICS:
                values = ", ".join(
                    f"p{p}={fmt_percentile(group, metric, p)}" for p in PERCENTILES
                )
                print(f"    {metric}: {values}")
            for label, predicate in rules:
                count, pct = count_rule(group, predicate)
                print(f"    {label}: {count}/{len(group)} ({pct:.2f}%)")

        print(f"  Rule overlap combinations by slice-thickness bin (old, n_for99>1, far>30>=1):")
        for bin_name in THICKNESS_BINS:
            group = [r for r in organ_rows if r["thickness_bin"] == bin_name]
            combos = {}
            for row in group:
                key = (
                    numeric(row, "n_components_all") > 20,
                    numeric(row, "n_for_99pct_volume") > 1,
                    numeric(row, "n_small_far_from_all_large_gt_30mm") >= 1,
                )
                combos[key] = combos.get(key, 0) + 1
            print(f"    {bin_name} mm:")
            for key in sorted(combos):
                print(f"      {key}: {combos[key]}")


def write_lists(rows, out_dir):
    out_dir = Path(out_dir)
    names = ("multi_large_pieces", "far_small_pieces", "old_rule_only")
    outputs = {(organ, name): out_dir / f"component_{organ}_{name}.txt"
               for organ in ("colon", "stomach") for name in names}
    existing = [str(path) for path in outputs.values() if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite existing lists: " + ", ".join(existing))
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = {key: [] for key in outputs}
    for row in rows:
        organ = row.get("organ")
        if organ not in ("colon", "stomach"):
            continue
        old = numeric(row, "n_components_all") > 20
        for name, condition in (
            ("multi_large_pieces", numeric(row, "n_ge_1ml") >= 3
             and numeric(row, "largest_component_fraction") < 0.8),
            ("far_small_pieces", numeric(row, "n_small_far_from_all_large_gt_30mm") >= 1),
            ("old_rule_only", old and numeric(row, "n_for_99pct_volume") == 1
             and numeric(row, "n_small_far_from_all_large_gt_10mm") == 0),
        ):
            if condition:
                cases[(organ, name)].append(row["case_id"])
    for key, path in outputs.items():
        ids = sorted(set(cases[key]))
        path.write_text("".join(f"{case}\n" for case in ids), encoding="utf-8")
        print(f"List {key[0]} {key[1]}: {len(ids)} cases -> {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-features", default=r"D:\PanTS_data\component_features_all.csv")
    parser.add_argument("--scored", default=r"D:\PanTS_data\scored_all.csv")
    parser.add_argument("--out-dir", default=r"D:\PanTS_data")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix=".component_summary_snapshot_",
                                     dir=Path(__file__).resolve().parent) as temp:
        temp = Path(temp)
        component_copy = snapshot_csv(args.component_features, temp / "component_features.csv")
        scored_copy = snapshot_csv(args.scored, temp / "scored.csv")
        component_rows = read_csv(component_copy)
        scored_rows = read_csv(scored_copy)
    rows, missing_score, empty_rows, other_errors = summarize(component_rows, scored_rows)
    print(f"Input component rows: {len(component_rows)}; scored snapshot rows: {len(scored_rows)}")
    print(f"Unmatched component rows: {missing_score}; empty-mask rows excluded: {empty_rows}; "
          f"other-error rows excluded: {other_errors}")
    print_summary(rows)
    write_lists(rows, args.out_dir)


if __name__ == "__main__":
    main()
