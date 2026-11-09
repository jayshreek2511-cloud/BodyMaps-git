"""Compute connectivity-26 component and physical-distance features for organ masks."""
import argparse
import csv
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import time

import numpy as np
from scipy import ndimage

from io_utils import load_nifti

ORGANS = ("stomach", "colon")
CONNECTIVITY = 3  # 26-neighborhood for scipy.ndimage.generate_binary_structure
FIELDS = [
    "case_id", "organ", "spacing_z", "n_components_all", "n_ge_0p1ml",
    "n_ge_1ml", "n_for_99pct_volume", "small_volume_fraction_1ml",
    "largest_component_fraction", "n_le_10_voxels", "small_dist_median_mm",
    "small_dist_max_mm", "n_small_far_gt_10mm", "n_small_far_gt_30mm",
    "small_volume_far_gt_10mm_fraction",
    "small_dist_to_nearest_large_median_mm",
    "small_dist_to_nearest_large_max_mm",
    "n_small_far_from_all_large_gt_10mm",
    "n_small_far_from_all_large_gt_30mm", "error",
]


def parse_cases(items):
    if not items:
        return None
    cases = set()
    for item in items:
        for part in item.split(","):
            if "-" in part:
                start, end = map(int, part.split("-", 1))
                if end < start:
                    raise ValueError(f"invalid case range: {part}")
                cases.update(range(start, end + 1))
            else:
                cases.add(int(part))
    return sorted(cases)


def component_features(mask, spacing):
    """Return all requested component and distance metrics for a binary mask."""
    mask = np.asarray(mask, dtype=bool)
    spacing = tuple(float(x) for x in spacing)
    voxel_ml = float(np.prod(spacing)) / 1000.0
    total_voxels = int(mask.sum())
    if total_voxels == 0:
        raise ValueError("empty_mask")

    labels, n_components = ndimage.label(
        mask, structure=ndimage.generate_binary_structure(3, CONNECTIVITY)
    )
    sizes = np.bincount(labels.ravel())[1:].astype(np.int64)
    volumes = sizes * voxel_ml
    largest_index = int(np.argmax(sizes)) + 1
    largest = labels == largest_index
    small_ids = np.flatnonzero(volumes < 1.0) + 1
    large_ids = np.flatnonzero(volumes >= 1.0) + 1

    cumulative = np.cumsum(np.sort(sizes)[::-1])
    n_for_99 = int(np.searchsorted(cumulative, 0.99 * total_voxels) + 1)
    small_volume = float(volumes[volumes < 1.0].sum())

    distances = []
    far_volume = 0.0
    far_10 = 0
    far_30 = 0
    nearest_large_distances = []
    nearest_large_far_10 = 0
    nearest_large_far_30 = 0
    if len(small_ids):
        coords = np.where(mask)
        lo = [max(0, int(axis.min()) - 10) for axis in coords]
        hi = [min(mask.shape[i], int(coords[i].max()) + 11) for i in range(3)]
        crop_slices = tuple(slice(lo[i], hi[i]) for i in range(3))
        crop_labels = labels[crop_slices]
        crop_largest = crop_labels == largest_index
        distance_mm = ndimage.distance_transform_edt(
            ~crop_largest, sampling=spacing
        )
        if len(large_ids):
            crop_large = np.isin(crop_labels, large_ids)
            distance_to_large_mm = ndimage.distance_transform_edt(
                ~crop_large, sampling=spacing
            )
        else:
            distance_to_large_mm = None
        for component_id in small_ids:
            minimum = float(distance_mm[crop_labels == component_id].min())
            distances.append(minimum)
            size = int(sizes[component_id - 1])
            if minimum > 10.0:
                far_10 += 1
                far_volume += size * voxel_ml
            if minimum > 30.0:
                far_30 += 1
            if distance_to_large_mm is not None:
                nearest_large = float(
                    distance_to_large_mm[crop_labels == component_id].min()
                )
                nearest_large_distances.append(nearest_large)
                nearest_large_far_10 += nearest_large > 10.0
                nearest_large_far_30 += nearest_large > 30.0

    return {
        "n_components_all": int(n_components),
        "n_ge_0p1ml": int(np.count_nonzero(volumes >= 0.1)),
        "n_ge_1ml": int(np.count_nonzero(volumes >= 1.0)),
        "n_for_99pct_volume": n_for_99,
        "small_volume_fraction_1ml": small_volume / (total_voxels * voxel_ml),
        "largest_component_fraction": float(sizes.max() / total_voxels),
        "n_le_10_voxels": int(np.count_nonzero(sizes <= 10)),
        "small_dist_median_mm": float(np.median(distances)) if distances else 0.0,
        "small_dist_max_mm": float(np.max(distances)) if distances else 0.0,
        "n_small_far_gt_10mm": far_10,
        "n_small_far_gt_30mm": far_30,
        "small_volume_far_gt_10mm_fraction": far_volume / (total_voxels * voxel_ml),
        "small_dist_to_nearest_large_median_mm": (
            float(np.median(nearest_large_distances)) if nearest_large_distances else 0.0),
        "small_dist_to_nearest_large_max_mm": (
            float(np.max(nearest_large_distances)) if nearest_large_distances else 0.0),
        "n_small_far_from_all_large_gt_10mm": int(nearest_large_far_10),
        "n_small_far_from_all_large_gt_30mm": int(nearest_large_far_30),
        "volume_ml": total_voxels * voxel_ml,
        "voxel_volume_ml": voxel_ml,
    }


def case_rows(args):
    root, number = args
    case_id = f"PanTS_{number:08d}"
    result = []
    for organ in ORGANS:
        path = Path(root) / case_id / "segmentations" / f"{organ}.nii.gz"
        row = {"case_id": case_id, "organ": organ, "error": ""}
        if not path.is_file():
            row["error"] = f"missing_file:{path.name}"
            result.append(row)
            continue
        volume, spacing, error = load_nifti(path)
        if error:
            row["error"] = error
            result.append(row)
            continue
        row["spacing_z"] = round(float(spacing[2]), 3)
        try:
            row.update(component_features(volume != 0, spacing))
        except Exception as exc:
            row["error"] = str(exc) if str(exc) else type(exc).__name__
        result.append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\PanTS_data\labels")
    parser.add_argument("--layout", choices=("flat",), default="flat")
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--out", default=r"D:\PanTS_data\component_features_all.csv")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--log", default=r"D:\PanTS_data\component_study\component_features_all.log")
    args = parser.parse_args()
    root, out, log_path = Path(args.root), Path(args.out), Path(args.log)
    selected = parse_cases(args.cases)
    if selected is None:
        selected = sorted(int(p.name.split("_")[-1])
                          for p in root.glob("PanTS_????????") if p.is_dir())
    if out.exists() and not args.resume:
        parser.error(f"output exists; use --resume or choose another path: {out}")
    done = set()
    if args.resume and out.exists():
        with out.open(newline="", encoding="utf-8") as stream:
            done = {(r["case_id"], r["organ"]) for r in csv.DictReader(stream)}
    pending = [number for number in selected
               if any((f"PanTS_{number:08d}", organ) not in done for organ in ORGANS)]
    out.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    append = args.resume and out.exists() and out.stat().st_size > 0
    start_time = time.perf_counter()
    case_completion_times = []
    rows_written = 0
    with out.open("a" if append else "w", newline="", encoding="utf-8") as stream, \
            log_path.open("a", encoding="utf-8") as log:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        if not append:
            writer.writeheader()
            stream.flush()
        with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
            for rows in pool.map(case_rows, [(str(root), n) for n in pending]):
                for row in rows:
                    if args.resume and (row["case_id"], row["organ"]) in done:
                        continue
                    writer.writerow(row)
                    stream.flush()
                    rows_written += 1
                    if row["error"]:
                        log.write(f"{row['case_id']}\t{row['organ']}\t{row['error']}\n")
                        log.flush()
                    print(f"Wrote {row['case_id']} {row['organ']}: "
                          f"{row['error'] or 'ok'}", flush=True)
                case_completion_times.append(time.perf_counter() - start_time)
    total_seconds = time.perf_counter() - start_time
    if len(case_completion_times) > 10:
        steady = ((case_completion_times[-1] - case_completion_times[9])
                  / (len(case_completion_times) - 10))
    else:
        steady = total_seconds / max(len(case_completion_times), 1)
    print(f"Completed {rows_written} organ rows in {total_seconds:.2f}s; "
          f"steady seconds/case after first 10: {steady:.3f}; "
          f"output: {out}; log: {log_path}")


if __name__ == "__main__":
    main()
