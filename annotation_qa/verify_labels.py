"""Compare separate organ-mask voxel counts with combined labels."""
import argparse
import math
from pathlib import Path

import nibabel as nib
import numpy as np

from config import LABEL_IDS

ORGANS = (("stomach", "stomach.nii.gz", LABEL_IDS["stomach"]),
          ("colon", "colon.nii.gz", LABEL_IDS["colon"]))
GROUP_ORDER = (">5%", "2-5%", "<2% (ok)")


def relative_difference(separate_count, combined_count):
    """Return absolute percent difference relative to the combined-label count."""
    if separate_count is None or combined_count is None:
        return math.inf
    if combined_count == 0:
        return 0.0 if separate_count == 0 else math.inf
    return 100.0 * abs(separate_count - combined_count) / combined_count


def counts_for_case(case):
    errors = []
    combined_path = case / "combined_labels.nii.gz"
    try:
        combined = np.asanyarray(nib.load(str(combined_path)).dataobj)
        combined_counts = {name: int(np.count_nonzero(combined == label_id))
                           for name, _, label_id in ORGANS}
    except Exception as exc:
        combined_counts = {name: None for name, _, _ in ORGANS}
        errors.append(f"combined_file_error:{type(exc).__name__}")
    result = {}
    for name, filename, _ in ORGANS:
        path = case / "segmentations" / filename
        try:
            separate = np.asanyarray(nib.load(str(path)).dataobj)
            separate_count = int(np.count_nonzero(separate))
        except Exception as exc:
            separate_count = None
            errors.append(f"{name}_file_error:{type(exc).__name__}")
        combined_count = combined_counts[name]
        result[name] = (
            separate_count, combined_count,
            relative_difference(separate_count, combined_count),
        )
    result["errors"] = errors
    return result


def group_for(result):
    worst = max(result[name][2] for name, _, _ in ORGANS)
    if worst < 2:
        return "<2% (ok)"
    if worst <= 5:
        return "2-5%"
    return ">5%"


def organ_file_audit(cases):
    union = set()
    per_case = {}
    for case in cases:
        files = {p.name for p in (case / "segmentations").glob("*.nii.gz")}
        union.update(files)
        per_case[case.name] = files
    return [(case_id, sorted(union - files))
            for case_id, files in per_case.items() if len(files) == 27]


def _pct(value):
    return "NA" if not math.isfinite(value) else f"{value:.3f}%"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\PanTS_data\labels")
    parser.add_argument("--n", type=int, default=50)
    args = parser.parse_args(argv)
    if args.n < 0:
        parser.error("--n must be nonnegative")
    root = Path(args.root)
    all_cases = sorted((p for p in root.glob("PanTS_*") if p.is_dir()),
                       key=lambda p: p.name)
    selected = all_cases[:args.n]
    results = {case.name: counts_for_case(case) for case in selected}
    groups = {name: [] for name in GROUP_ORDER}
    for case in selected:
        result = results[case.name]
        groups[group_for(result)].append((case.name, result))

    print("GROUP_COUNTS (case grouped by its worst organ difference):")
    for group in GROUP_ORDER:
        print(f"{group}: {len(groups[group])}")
    print(">5% CASES:")
    if not groups[">5%"]:
        print("  none")
    for case_id, result in groups[">5%"]:
        stomach = result["stomach"]
        colon = result["colon"]
        detail = (f"stomach={_pct(stomach[2])} separate={stomach[0]} combined={stomach[1]}; "
                  f"colon={_pct(colon[2])} separate={colon[0]} combined={colon[1]}")
        if result["errors"]:
            detail += "; " + ";".join(result["errors"])
        print(f"  {case_id}: {detail}")

    case_audit = organ_file_audit(all_cases)
    print("27_ORGAN_FILE_CASES:")
    if not case_audit:
        print("  none")
    else:
        for case_id, missing in case_audit:
            print(f"  {case_id}: missing {', '.join(missing) if missing else 'unknown organ'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
