"""Stratified colon component-count sensitivity study across connectivities."""
import argparse
import csv
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage

from io_utils import load_nifti

THICKNESS_BINS = ("<=1", "1-3", "3-5", ">5")
COMPONENT_BINS = ("0-5", "6-20", "21-50", ">50")
CONNECTIVITIES = (1, 2, 3)
CONNECTIVITY_NEIGHBORS = {1: 6, 2: 18, 3: 26}


def thickness_bin(value):
    value = float(value)
    if value <= 1:
        return "<=1"
    if value <= 3:
        return "1-3"
    if value <= 5:
        return "3-5"
    return ">5"


def component_bin(value):
    value = int(float(value))
    if value <= 5:
        return "0-5"
    if value <= 20:
        return "6-20"
    if value <= 50:
        return "21-50"
    return ">50"


def metric_fields():
    fields = ["case_id", "sample_thickness_bin", "sample_component_bin",
              "error", "spacing_x", "spacing_y", "spacing_z",
              "slice_thickness_bin", "voxel_volume_ml", "volume_ml"]
    for conn in CONNECTIVITIES:
        fields.extend([
            f"n_components_conn{conn}",
            f"largest_component_fraction_conn{conn}",
            f"n_ge_0p1ml_conn{conn}", f"n_ge_1ml_conn{conn}",
            f"n_ge_5ml_conn{conn}", f"n_le_10_voxels_conn{conn}",
            f"n_single_voxel_conn{conn}",
            f"small_volume_fraction_1ml_conn{conn}",
            f"n_for_99pct_volume_conn{conn}",
        ])
    return fields


def component_metrics(mask, spacing):
    """Return component statistics for connectivities 6, 18 and 26."""
    mask = np.asarray(mask, dtype=bool)
    voxel_ml = float(np.prod(spacing)) / 1000.0
    total = int(mask.sum())
    result = {}
    for conn in CONNECTIVITIES:
        labels, n = ndimage.label(mask, structure=ndimage.generate_binary_structure(3, conn))
        sizes = np.bincount(labels.ravel())[1:].astype(np.int64)
        volumes = sizes * voxel_ml
        suffix = f"conn{conn}"
        result[f"n_components_{suffix}"] = int(n)
        result[f"largest_component_fraction_{suffix}"] = (
            float(sizes.max() / total) if total else 0.0)
        result[f"n_ge_0p1ml_{suffix}"] = int(np.count_nonzero(volumes >= 0.1))
        result[f"n_ge_1ml_{suffix}"] = int(np.count_nonzero(volumes >= 1.0))
        result[f"n_ge_5ml_{suffix}"] = int(np.count_nonzero(volumes >= 5.0))
        result[f"n_le_10_voxels_{suffix}"] = int(np.count_nonzero(sizes <= 10))
        result[f"n_single_voxel_{suffix}"] = int(np.count_nonzero(sizes == 1))
        result[f"small_volume_fraction_1ml_{suffix}"] = (
            float(volumes[volumes < 1.0].sum() / (total * voxel_ml))
            if total else 0.0)
        if total:
            descending = np.sort(sizes)[::-1]
            count_99 = int(np.searchsorted(np.cumsum(descending), 0.99 * total) + 1)
        else:
            count_99 = 0
        result[f"n_for_99pct_volume_{suffix}"] = count_99
    return result


def select_sample(scores_path, per_cell=30):
    with Path(scores_path).open(newline="", encoding="utf-8") as stream:
        rows = [r for r in csv.DictReader(stream) if r.get("organ") == "colon"]
    cells = {(t, c): [] for t in THICKNESS_BINS for c in COMPONENT_BINS}
    for row in rows:
        try:
            tbin = thickness_bin(row["spacing_z"])
            cbin = component_bin(row["n_components"])
        except (KeyError, TypeError, ValueError):
            continue
        cells[(tbin, cbin)].append(row)
    rng = np.random.default_rng(42)
    selected = []
    for tbin in THICKNESS_BINS:
        for cbin in COMPONENT_BINS:
            cell = sorted(cells[(tbin, cbin)], key=lambda r: r["case_id"])
            n = min(per_cell, len(cell))
            if n:
                chosen = rng.choice(len(cell), size=n, replace=False)
                selected.extend((cell[int(i)], tbin, cbin) for i in sorted(chosen))
            print(f"sample {tbin} mm x {cbin} components: {n}/{len(cell)}")
    return selected


def process_case(args):
    root, row, tbin, cbin = args
    case_id = row["case_id"]
    number = int(case_id.split("_")[-1])
    path = Path(root) / case_id / "segmentations" / "colon.nii.gz"
    data, spacing, error = load_nifti(path)
    out = {"case_id": case_id, "sample_thickness_bin": tbin,
           "sample_component_bin": cbin, "error": error or ""}
    if error:
        return out
    try:
        image = nib.as_closest_canonical(nib.load(str(path)))
        spacing = tuple(float(x) for x in spacing)
        mask = np.asarray(data != 0)
        voxel_ml = float(np.prod(spacing)) / 1000.0
        out.update({"spacing_x": spacing[0], "spacing_y": spacing[1],
                    "spacing_z": spacing[2],
                    "slice_thickness_bin": thickness_bin(spacing[2]),
                    "voxel_volume_ml": voxel_ml,
                    "volume_ml": int(mask.sum()) * voxel_ml})
        out.update(component_metrics(mask, spacing))
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=r"D:\PanTS_data\labels")
    parser.add_argument("--scores", default=r"D:\PanTS_data\scored_all.csv")
    parser.add_argument("--out", default=r"D:\PanTS_data\component_study\component_sensitivity.csv")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--per-cell", type=int, default=30)
    args = parser.parse_args()
    sample = select_sample(args.scores, args.per_cell)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.resume and out.exists():
        with out.open(newline="", encoding="utf-8") as stream:
            done = {r["case_id"] for r in csv.DictReader(stream)}
    elif out.exists():
        parser.error(f"output already exists; use --resume or choose another path: {out}")
    pending = [(str(args.root), row, tbin, cbin) for row, tbin, cbin in sample
               if row["case_id"] not in done]
    append = args.resume and out.exists() and out.stat().st_size > 0
    with out.open("a" if append else "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=metric_fields())
        if not append:
            writer.writeheader()
            stream.flush()
        with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
            for result in pool.map(process_case, pending):
                writer.writerow(result)
                stream.flush()
                print(f"Wrote {result['case_id']}: {result.get('error') or 'ok'}", flush=True)
    print(f"Completed {len(pending)} sampled cases; output: {out}")


if __name__ == "__main__":
    main()
