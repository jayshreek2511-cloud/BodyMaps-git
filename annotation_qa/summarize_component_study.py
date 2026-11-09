"""Summarize a stratified colon component sensitivity sample."""
import argparse
import csv
from pathlib import Path
import struct
import zlib

import nibabel as nib
import numpy as np
from scipy import ndimage

from io_utils import load_nifti
from component_sensitivity import CONNECTIVITY_NEIGHBORS


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def num(row, key):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return 0.0


def save_png(path, rgb, title):
    height, width, _ = rgb.shape
    raw = b"".join(b"\0" + rgb[y].tobytes() for y in range(height))

    def chunk(kind, data):
        return (struct.pack("!I", len(data)) + kind + data
                + struct.pack("!I", zlib.crc32(kind + data) & 0xffffffff))

    image = (b"\x89PNG\r\n\x1a\n"
             + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0))
             + chunk(b"tEXt", b"Title\0" + title.encode("ascii", "replace"))
             + chunk(b"IDAT", zlib.compress(raw, 5))
             + chunk(b"IEND", b""))
    Path(path).write_bytes(image)


def print_details(rows, root, out_dir, limit=6):
    candidates = [r for r in rows
                  if r.get("slice_thickness_bin") == "<=1"
                  and num(r, "n_components_conn3") > 20
                  and num(r, "n_ge_1ml_conn3") <= 5
                  and not r.get("error")]
    candidates.sort(key=lambda r: r["case_id"])
    rng = np.random.default_rng(42)
    if len(candidates) > limit:
        candidates = [candidates[i] for i in sorted(
            rng.choice(len(candidates), limit, replace=False))]
    print(f"Thin-slice detail cases meeting criteria: {len(candidates)} of requested {limit}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for row in candidates:
        case = row["case_id"]
        path = Path(root) / case / "segmentations" / "colon.nii.gz"
        volume, spacing, error = load_nifti(path)
        if error:
            print(f"{case}: cannot reload for detail: {error}")
            continue
        mask = volume != 0
        image = nib.as_closest_canonical(nib.load(str(path)))
        labels, n = ndimage.label(mask, structure=ndimage.generate_binary_structure(3, 3))
        sizes = np.bincount(labels.ravel())[1:].astype(np.int64)
        centers = ndimage.center_of_mass(mask, labels, range(1, n + 1)) if n else []
        voxel_ml = float(np.prod(spacing)) / 1000.0
        print(f"\n{case}: components={n}, voxel_volume_ml={voxel_ml:.8g}")
        for idx, (size, center) in enumerate(zip(sizes, centers), start=1):
            world = image.affine @ np.r_[center, 1.0]
            print(f"  component {idx}: volume_ml={size * voxel_ml:.8g}; "
                  f"centroid_mm=({world[0]:.3f}, {world[1]:.3f}, {world[2]:.3f})")
        small_ids = np.flatnonzero(sizes * voxel_ml < 1.0) + 1
        small_pixels = np.isin(labels, small_ids)
        per_slice = small_pixels.sum(axis=(0, 1))
        z = int(np.argmax(per_slice)) if len(per_slice) else 0
        axial = mask[:, :, z].T
        small_axial = small_pixels[:, :, z].T
        rgb = np.zeros((*axial.shape, 3), dtype=np.uint8)
        rgb[axial] = (150, 150, 150)
        rgb[small_axial] = (255, 0, 0)
        dest = out_dir / f"{case}_colon_components.png"
        save_png(dest, rgb, f"{case} colon components; axial RAS z index {z}; small components <1 mL")
        print(f"  axial image: {dest}; z={z}; small-component pixels={int(small_axial.sum())}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=r"D:\PanTS_data\component_study\component_sensitivity.csv")
    parser.add_argument("--root", default=r"D:\PanTS_data\labels")
    parser.add_argument("--out-dir", default=r"D:\PanTS_data\component_study")
    args = parser.parse_args()
    rows = read_rows(args.input)
    if not rows:
        parser.error("component study CSV has no rows")
    print("WARNING: this is a stratified sample; percentages describe the sample, not the whole dataset.")
    bins = ("<=1", "1-3", "3-5", ">5")
    for thickness in bins:
        group = [r for r in rows if r.get("slice_thickness_bin") == thickness and not r.get("error")]
        print(f"\nSlice thickness {thickness} mm: n={len(group)}")
        for conn in (1, 2, 3):
            values = np.array([num(r, f"n_components_conn{conn}") for r in group])
            mean = float(values.mean()) if len(values) else float("nan")
            median = float(np.median(values)) if len(values) else float("nan")
            print(f"  connectivity {CONNECTIVITY_NEIGHBORS[conn]}: "
                  f"n_components mean={mean:.3f}, median={median:.3f}")

    definitions = [
        ("conn6 all", "n_components_conn1"),
        ("conn18 all", "n_components_conn2"),
        ("conn26 all", "n_components_conn3"),
        ("conn26 components >=0.1 mL", "n_ge_0p1ml_conn3"),
        ("conn26 components >=1 mL", "n_ge_1ml_conn3"),
        ("conn26 components >=5 mL", "n_ge_5ml_conn3"),
        ("conn26 n_for_99pct_volume", "n_for_99pct_volume_conn3"),
    ]
    percent_by_definition = {}
    print("\nCases with more than 20 components (count / bin n / percent):")
    for label, key in definitions:
        rates = []
        print(f"  {label}:")
        for thickness in bins:
            group = [r for r in rows if r.get("slice_thickness_bin") == thickness and not r.get("error")]
            count = sum(num(r, key) > 20 for r in group)
            rate = count / len(group) * 100 if group else 0.0
            rates.append(rate)
            print(f"    {thickness}: {count}/{len(group)} ({rate:.2f}%)")
        percent_by_definition[label] = rates
    print("\nThickness dependence (highest percent / lowest percent):")
    for label, rates in percent_by_definition.items():
        low = min(rates)
        ratio = f"{max(rates) / low:.3f}" if low > 0 else "undefined (lowest bin is 0%)"
        print(f"  {label}: {ratio}")

    print("\nMedian small-component counts by thickness and connectivity:")
    for thickness in bins:
        group = [r for r in rows if r.get("slice_thickness_bin") == thickness and not r.get("error")]
        print(f"  {thickness} mm:")
        for conn in (1, 2, 3):
            single = np.median([num(r, f"n_single_voxel_conn{conn}") for r in group]) if group else float("nan")
            le10 = np.median([num(r, f"n_le_10_voxels_conn{conn}") for r in group]) if group else float("nan")
            print(f"    conn{CONNECTIVITY_NEIGHBORS[conn]}: "
                  f"n_single_voxel={single:.1f}, n_le_10_voxels={le10:.1f}")

    print("\n94-style group (conn26 n_components >20 and largest fraction <0.5):")
    for thickness in bins:
        group = [r for r in rows if r.get("slice_thickness_bin") == thickness and not r.get("error")]
        count = sum(num(r, "n_components_conn3") > 20
                    and num(r, "largest_component_fraction_conn3") < 0.5 for r in group)
        print(f"  {thickness} mm: {count}/{len(group)}")
    print_details(rows, args.root, args.out_dir)


if __name__ == "__main__":
    main()
