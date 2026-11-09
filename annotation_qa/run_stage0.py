"""Extract Stage 0 label-only features from local PanTS masks."""
import argparse
import csv
import multiprocessing as mp
from pathlib import Path

import numpy as np

from checks import technical_error
from config import LABEL_IDS, ORGANS_TO_EVALUATE
from features import extract_features
from io_utils import load_nifti


def parse_cases(items):
    if not items:
        return None
    result = set()
    for item in items:
        if "-" in item:
            start, end = map(int, item.split("-", 1))
            result.update(range(start, end + 1))
        else:
            result.add(int(item))
    return result


def process_case(args):
    case, combined_path, overrides, source = args
    ids = dict(LABEL_IDS)
    ids.update(overrides)
    combined, spacing, combined_error = load_nifti(combined_path)
    if combined_error:
        return ([{"case_id": case, "organ": organ,
                  "technical_error": technical_error({}, organ, file_error=combined_error)}
                 for organ in ORGANS_TO_EVALUATE], None, combined_error)
    present = sorted(int(x) for x in np.unique(combined))
    shape = tuple(int(x) for x in combined.shape)
    metadata = {
        "shape_x": shape[0], "shape_y": shape[1], "shape_z": shape[2],
        "spacing_x": spacing[0], "spacing_y": spacing[1], "spacing_z": spacing[2],
        "label_ids_present": ",".join(str(x) for x in present),
    }
    rows = []
    for organ in ORGANS_TO_EVALUATE:
        label_id = ids[organ]
        organ_mask = None
        file_error = None
        missing = False
        if source == "separate":
            separate_path = Path(combined_path).parent / "segmentations" / f"{organ}.nii.gz"
            if not separate_path.is_file():
                missing = True
            else:
                separate, separate_spacing, file_error = load_nifti(separate_path)
                if not file_error and (separate.shape != combined.shape
                                       or not np.allclose(separate_spacing, spacing, rtol=1e-4, atol=1e-4)):
                    file_error = "separate_mask_geometry_mismatch"
                if not file_error:
                    organ_mask = separate != 0
        if missing:
            rows.append({"case_id": case, "organ": organ, "label_id": label_id,
                         **metadata, "technical_error": technical_error(
                             {}, organ, missing_organ_file=True)})
            continue
        if file_error:
            rows.append({"case_id": case, "organ": organ, "label_id": label_id,
                         **metadata, "technical_error": technical_error(
                             {}, organ, file_error=file_error)})
            continue
        features = extract_features(
            combined, label_id, spacing, combined, label_ids=ids, organ_mask=organ_mask
        )
        rows.append({"case_id": case, "organ": organ, "label_id": label_id,
                     **metadata, **features,
                     "technical_error": technical_error(features, organ)})
    return rows, present, None


def columns():
    return ["case_id", "organ", "label_id", "technical_error",
      "shape_x", "shape_y", "shape_z", "spacing_x", "spacing_y", "spacing_z",
      "label_ids_present", "volume_ml", "bbox_x_mm", "bbox_y_mm", "bbox_z_mm",
      "bbox_fill_ratio", "n_components", "largest_component_fraction",
      "n_small_fragments", "fragment_volume_fraction",
      "overlap_other_labels_fraction", "overlap_top1_label", "overlap_top1_fraction",
      "overlap_top2_label", "overlap_top2_fraction", "combined_vs_separate_ratio",
      "touches_scan_edge_x_min", "touches_scan_edge_x_max",
      "touches_scan_edge_y_min", "touches_scan_edge_y_max",
      "touches_scan_edge_z_min", "touches_scan_edge_z_max", "any_edge_touch",
      "centroid_x_mm", "centroid_y_mm", "centroid_z_mm",
      "centroid_rel_x", "centroid_rel_y", "centroid_rel_z", "left_right_side",
      "holes_fraction", "surface_area_mm2", "compactness",
      "contact_liver_fraction", "contact_spleen_fraction",
      "contact_kidney_left_fraction", "contact_kidney_right_fraction",
      "contact_pancreas_fraction", "contact_duodenum_fraction",
      "contact_other_pair_organ_fraction", "contact_background_fraction",
      "z_extent_mm", "z_extent_fraction_total_labeled"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--layout", choices=("mask_only", "flat"), default="mask_only")
    p.add_argument("--source", choices=("combined", "separate"), default="separate")
    p.add_argument("--out", default="features.csv")
    p.add_argument("--cases", nargs="+", help="case numbers/ranges, e.g. 1-10 909")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--label-id", action="append", default=[], metavar="ORGAN=ID")
    a = p.parse_args(argv)
    if a.workers < 1:
        p.error("--workers must be at least 1")
    overrides = {}
    try:
        for item in a.label_id:
            name, value = item.split("=", 1)
            if name not in LABEL_IDS:
                raise ValueError(f"unknown label name: {name}")
            overrides[name] = int(value)
        wanted = parse_cases(a.cases)
    except ValueError as exc:
        p.error(str(exc))
    root = Path(a.root)
    pattern = ("mask_only/PanTS_*/combined_labels.nii.gz" if a.layout == "mask_only"
               else "PanTS_*/combined_labels.nii.gz")
    paths = sorted(root.glob(pattern))
    if wanted is not None:
        paths = [f for f in paths if int(f.parent.name.removeprefix("PanTS_")) in wanted]
    if not paths:
        subtree = root / ("mask_only" if a.layout == "mask_only" else "")
        p.error(f"no matching masks found under {subtree}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if a.resume and out.exists():
        with out.open(newline="", encoding="utf-8") as f:
            done = {(r["case_id"], r["organ"]) for r in csv.DictReader(f) if r.get("case_id")}
    pending = [(f.parent.name, f, overrides, a.source) for f in paths]
    if a.resume:
        pending = [x for x in pending if not all((x[0], o) in done for o in ORGANS_TO_EVALUATE)]
    fresh = not out.exists() or out.stat().st_size == 0
    first = True
    with out.open("a", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=columns(), extrasaction="ignore")
        if fresh:
            writer.writeheader()
            target.flush()
        pool = mp.Pool(a.workers) if a.workers > 1 else None
        iterator = pool.imap(process_case, pending) if pool else map(process_case, pending)
        try:
            for rows, present, error in iterator:
                for row in rows:
                    if a.resume and (row["case_id"], row["organ"]) in done:
                        continue
                    writer.writerow(row)
                    target.flush()
                if first and present is not None:
                    print(f"Label ids present in first case {rows[0]['case_id']}: {present}")
                    first = False
                if error:
                    with (Path(__file__).with_name("errors.log")).open("a", encoding="utf-8") as log:
                        log.write(f"{rows[0]['case_id']}: {error}\n")
        finally:
            if pool:
                pool.close()
                pool.join()
    print(f"Wrote results to {out}")


if __name__ == "__main__":
    main()
