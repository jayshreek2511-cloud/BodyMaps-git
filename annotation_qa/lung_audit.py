"""Label-only spatial audit of separate lung and nearby organ masks."""
import argparse
import csv
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import nibabel as nib
import numpy as np

ORGANS = ("lung_left", "lung_right", "colon", "stomach", "liver",
          "kidney_left", "kidney_right")
LUNGS = ("lung_left", "lung_right")
TARGETS = ("colon", "stomach", "liver", "kidneys")


def parse_cases(items):
    if not items:
        return None
    result = set()
    for item in items:
        for part in item.split(","):
            if "-" in part:
                lo, hi = map(int, part.split("-", 1))
                if hi < lo:
                    raise ValueError(f"invalid case range: {part}")
                result.update(range(lo, hi + 1))
            else:
                result.add(int(part))
    return sorted(result)


def _centroid_z(mask, affine):
    points = np.argwhere(mask)
    if not len(points):
        return None
    center = points.mean(axis=0)
    return float((affine @ np.r_[center, 1.0])[2])


def _z_limits(mask, affine):
    occupied = np.flatnonzero(mask.any(axis=(0, 1)))
    if not len(occupied):
        return None, None
    z0, z1 = int(occupied[0]), int(occupied[-1])
    return (float((affine @ [0, 0, z0, 1])[2]),
            float((affine @ [0, 0, z1, 1])[2]))


def build_row(case_id, masks, affine, spacing, errors=None):
    """Summarize already RAS-oriented binary arrays on one common grid."""
    errors = list(errors or [])
    kidney_masks = [masks.get("kidney_left"), masks.get("kidney_right")]
    kidney_masks = [m for m in kidney_masks if m is not None]
    masks = dict(masks)
    masks["kidneys"] = (np.logical_or.reduce(kidney_masks)
                        if kidney_masks else None)
    row = {"case_id": case_id, "error": "; ".join(errors),
           "n_lungs_empty": 0}
    centroids = {}
    counts = {}
    for name in ORGANS:
        mask = masks.get(name)
        count = int(mask.sum()) if mask is not None else None
        counts[name] = count
        row[f"{name}_voxels"] = count
        row[f"{name}_volume_ml"] = (count * float(np.prod(spacing)) / 1000
                                     if count is not None else None)
        row[f"{name}_empty"] = (count == 0 if count is not None else None)
        centroids[name] = (_centroid_z(mask, affine)
                           if mask is not None and count else None)
        row[f"{name}_centroid_z_mm"] = centroids[name]
        z0, z1 = (_z_limits(mask, affine) if mask is not None else (None, None))
        row[f"{name}_z_min_mm"] = z0
        row[f"{name}_z_max_mm"] = z1
    row["n_lungs_empty"] = sum(counts[name] == 0 for name in LUNGS
                               if counts[name] is not None)
    kidney_centers = [centroids[n] for n in ("kidney_left", "kidney_right")
                      if centroids[n] is not None]
    row["kidney_centroid_z_mm"] = (float(np.mean(kidney_centers))
                                   if kidney_centers else None)

    for lung_name in LUNGS:
        lung = masks.get(lung_name)
        for target in TARGETS:
            other = masks.get(target)
            if lung is None or other is None:
                overlap = None
            elif lung.shape != other.shape:
                overlap = None
                errors.append(f"shape_mismatch:{lung_name}:{target}")
            else:
                overlap = int(np.count_nonzero(lung & other))
            row[f"{lung_name}_overlap_{target}_voxels"] = overlap
            row[f"{lung_name}_overlap_{target}_fraction_of_lung"] = (
                overlap / counts[lung_name]
                if overlap is not None and counts[lung_name] else
                (0.0 if overlap == 0 else None))
            denominator_name = "colon" if target == "colon" else target
            denominator = (counts.get(denominator_name)
                           if denominator_name != "kidneys"
                           else (int(masks["kidneys"].sum())
                                 if masks["kidneys"] is not None else None))
            row[f"{lung_name}_overlap_{target}_fraction_of_{target}"] = (
                overlap / denominator if overlap is not None and denominator
                else (0.0 if overlap == 0 else None))
        liver_z = centroids["liver"]
        kidney_z = row["kidney_centroid_z_mm"]
        row[f"{lung_name}_centroid_below_liver"] = (
            centroids[lung_name] < liver_z
            if centroids[lung_name] is not None and liver_z is not None else None)
        row[f"{lung_name}_centroid_below_kidney"] = (
            centroids[lung_name] < kidney_z
            if centroids[lung_name] is not None and kidney_z is not None else None)
    row["error"] = "; ".join(dict.fromkeys(errors))
    return row


def process_case(args):
    root, number = args
    case_id = f"PanTS_{number:08d}"
    arrays, images, errors = {}, {}, []
    for organ in ORGANS:
        path = Path(root) / case_id / "segmentations" / f"{organ}.nii.gz"
        if not path.is_file():
            arrays[organ] = None
            errors.append(f"missing:{organ}")
            continue
        try:
            image = nib.as_closest_canonical(nib.load(str(path)))
            arr = np.asanyarray(image.dataobj)
            if arr.ndim != 3:
                raise ValueError(f"expected 3D, got {arr.ndim}D")
            arrays[organ] = arr != 0
            images[organ] = image
        except Exception as exc:
            arrays[organ] = None
            errors.append(f"unreadable:{organ}:{type(exc).__name__}")
    ref = next(iter(images.values()), None)
    if ref is None:
        return build_row(case_id, arrays, np.eye(4), (1, 1, 1), errors)
    for organ, image in images.items():
        if (image.shape != ref.shape
                or not np.allclose(image.affine, ref.affine, rtol=0, atol=1e-4)):
            errors.append(f"geometry_mismatch:{organ}")
            arrays[organ] = None
    spacing = tuple(float(v) for v in nib.affines.voxel_sizes(ref.affine))
    return build_row(case_id, arrays, ref.affine, spacing, errors)


def fieldnames():
    names = ["case_id", "error", "n_lungs_empty"]
    for organ in ORGANS:
        names += [f"{organ}_voxels", f"{organ}_volume_ml", f"{organ}_empty",
                  f"{organ}_centroid_z_mm", f"{organ}_z_min_mm",
                  f"{organ}_z_max_mm"]
    names.append("kidney_centroid_z_mm")
    for lung in LUNGS:
        for target in TARGETS:
            names += [f"{lung}_overlap_{target}_voxels",
                      f"{lung}_overlap_{target}_fraction_of_lung",
                      f"{lung}_overlap_{target}_fraction_of_{target}"]
        names += [f"{lung}_centroid_below_liver",
                  f"{lung}_centroid_below_kidney"]
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--layout", choices=("flat",), default="flat")
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", default=str(Path(__file__).with_name("lung_audit.csv")))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root, out = Path(args.root), Path(args.out)
    selected = parse_cases(args.cases)
    if selected is None:
        selected = sorted(int(p.name.split("_")[-1]) for p in root.glob("PanTS_????????")
                          if p.is_dir())
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.resume and out.exists():
        with out.open(newline="", encoding="utf-8") as stream:
            done = {int(r["case_id"].split("_")[-1])
                    for r in csv.DictReader(stream) if r.get("case_id")}
    pending = [n for n in selected if n not in done]
    exists = out.exists() and out.stat().st_size > 0
    with out.open("a" if exists else "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames())
        if not exists:
            writer.writeheader()
            stream.flush()
        with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
            for row in pool.map(process_case, [(str(root), n) for n in pending]):
                writer.writerow(row)
                stream.flush()
                print(f"Wrote {row['case_id']}: {row['error'] or 'ok'}", flush=True)
    print(f"Audit rows written: {len(pending)}; output: {out}")


if __name__ == "__main__":
    main()
