"""Build a reproducible, thickness-stratified visual validation shortlist."""
import argparse
import csv
import importlib.util
from pathlib import Path
import random
import sys
import tempfile

SEED = 42
ORGAN_NAMES = ("colon", "stomach")
BIN_NAMES = ("<=1", "1-3", "3-5", ">5")
GROUP_NAMES = ("old_rule_only", "new_feature_only", "both", "neither")
OUTPUT_COLUMNS = (
    "case_id", "organ", "spacing_z", "group",
    "old_rule_flag", "n_for_99pct_volume_gt_1_flag", "far_gt_30mm_flag",
    "n_components_all", "n_ge_1ml", "n_for_99pct_volume",
    "largest_component_fraction", "n_small_far_from_all_large_gt_30mm",
)


def load_summarizer():
    path = Path(__file__).with_name("summarize_component_features.py")
    spec = importlib.util.spec_from_file_location("component_summary", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def categorize(row, summary):
    old = summary.numeric(row, "n_components_all") > 20
    many_for_99 = summary.numeric(row, "n_for_99pct_volume") > 1
    far30 = summary.numeric(row, "n_small_far_from_all_large_gt_30mm") >= 1
    if old and not many_for_99 and not far30:
        group = "old_rule_only"
    elif old and (many_for_99 or far30):
        group = "both"
    elif not old and (many_for_99 or far30):
        group = "new_feature_only"
    else:
        group = "neither"
    return old, many_for_99, far30, group


def stratified_sample(rows, target, rng):
    by_bin = {name: [] for name in BIN_NAMES}
    for row in rows:
        by_bin[row["thickness_bin"]].append(row)
    for name in BIN_NAMES:
        by_bin[name].sort(key=lambda r: r["case_id"])
        rng.shuffle(by_bin[name])
    picked = []
    # Round-robin across non-empty bins balances selections while respecting availability.
    while len(picked) < min(target, len(rows)):
        advanced = False
        for name in BIN_NAMES:
            if by_bin[name] and len(picked) < min(target, len(rows)):
                picked.append(by_bin[name].pop())
                advanced = True
        if not advanced:
            break
    return picked


def load_reference_lists(directory):
    references = {}
    for organ in ORGAN_NAMES:
        for group in ("old_rule_only", "far_small_pieces", "multi_large_pieces"):
            path = Path(directory) / f"component_{organ}_{group}.txt"
            if path.exists():
                references[(organ, group)] = {
                    line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                }
            else:
                references[(organ, group)] = None
    return references


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-features", default=r"D:\PanTS_data\component_features_all.csv")
    parser.add_argument("--scored", default=r"D:\PanTS_data\scored_all.csv")
    parser.add_argument("--lists-dir", default=r"D:\PanTS_data")
    parser.add_argument("--out", default=r"D:\PanTS_data\visual_validation_shortlist.csv")
    parser.add_argument("--per-group", type=int, default=5)
    args = parser.parse_args()
    if args.per_group < 1:
        parser.error("--per-group must be at least 1")
    out = Path(args.out)
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing shortlist: {out}")

    summary = load_summarizer()
    with tempfile.TemporaryDirectory(prefix=".shortlist_snapshot_", dir=Path(__file__).parent) as td:
        td = Path(td)
        component_copy = summary.snapshot_csv(args.component_features, td / "component.csv")
        scored_copy = summary.snapshot_csv(args.scored, td / "scored.csv")
        feature_rows = summary.read_csv(component_copy)
        scored_rows = summary.read_csv(scored_copy)
    feature_keys = [(r.get("case_id", ""), r.get("organ", "")) for r in feature_rows]
    scored_keys = [(r.get("case_id", ""), r.get("organ", "")) for r in scored_rows]
    if len(feature_keys) != len(set(feature_keys)):
        raise ValueError("Duplicate (case_id, organ) keys in component features CSV")
    if len(scored_keys) != len(set(scored_keys)):
        raise ValueError("Duplicate (case_id, organ) keys in scored CSV")

    valid_rows, unmatched, empty_rows, other_errors = summary.summarize(feature_rows, scored_rows)
    references = load_reference_lists(args.lists_dir)
    print(f"Input rows: component_features={len(feature_rows)}, scored={len(scored_rows)}")
    print(f"Join key=(case_id, organ); unmatched={unmatched}; empty-mask excluded={empty_rows}; other-error excluded={other_errors}")
    for key, case_ids in references.items():
        print(f"Existing list {key[0]}/{key[1]}: {'missing' if case_ids is None else len(case_ids)} IDs")

    rng = random.Random(SEED)
    chosen = []
    categorized = {organ: {group: [] for group in GROUP_NAMES} for organ in ORGAN_NAMES}
    for row in valid_rows:
        organ = row.get("organ")
        if organ not in ORGAN_NAMES:
            continue
        old, many_for_99, far30, group = categorize(row, summary)
        row = dict(row)
        row["old_rule_flag"] = int(old)
        row["n_for_99pct_volume_gt_1_flag"] = int(many_for_99)
        row["far_gt_30mm_flag"] = int(far30)
        row["group"] = group
        categorized[organ][group].append(row)

    print(f"Fixed random seed: {SEED}; requested per organ/group: {args.per_group}")
    for organ in ORGAN_NAMES:
        for group in GROUP_NAMES:
            available = categorized[organ][group]
            selected = stratified_sample(available, args.per_group, rng)
            chosen.extend(selected)
            print(f"\n{organ} / {group}: available={len(available)}, selected={len(selected)}")
            for bin_name in BIN_NAMES:
                n_available = sum(r["thickness_bin"] == bin_name for r in available)
                n_selected = sum(r["thickness_bin"] == bin_name for r in selected)
                print(f"  {bin_name} mm: available={n_available}, selected={n_selected}")
            print("  selected case IDs: " + (", ".join(r["case_id"] for r in selected) if selected else "(none)"))
            for list_name in ("old_rule_only", "far_small_pieces", "multi_large_pieces"):
                ids = references[(organ, list_name)]
                if ids is not None:
                    overlap = sum(r["case_id"] in ids for r in selected)
                    print(f"  selected IDs also in existing {list_name} list: {overlap}")

    seen = set()
    for row in chosen:
        key = (row["organ"], row["case_id"])
        if key in seen:
            raise RuntimeError(f"Duplicate selected case for organ: {key}")
        seen.add(key)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in chosen:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})
    print(f"\nShortlist rows written: {len(chosen)}")
    print(f"Output CSV: {out}")
    print("Output columns: " + ", ".join(OUTPUT_COLUMNS))


if __name__ == "__main__":
    main()
