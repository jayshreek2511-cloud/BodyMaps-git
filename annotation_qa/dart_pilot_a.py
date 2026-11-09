"""Pilot A: DART-Seg masks compared with the original separate-organ labels.

All inference outputs and CSVs are written outside the repository. Raw model masks
are preserved; the model card's optional component-cleaning snippet is not used.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel.processing import resample_from_to
from scipy import ndimage


SHORTLIST_DEFAULT = Path(r"D:\PanTS_data\visual_validation_shortlist.csv")
CT_ROOT_DEFAULT = Path(r"D:\PanTS_data\ct_review")
LABEL_ROOT_DEFAULT = Path(r"D:\PanTS_data\labels")
MODEL_DEFAULT = Path(r"D:\PanTS_data\dart_seg")
OUT_DEFAULT = Path(r"D:\PanTS_data\dart_pilot_a")
EXTRA_CASES = ("PanTS_00000001", "PanTS_00000004", "PanTS_00000040",
               "PanTS_00000043", "PanTS_00000112", "PanTS_00000170")
MAIN_PROMPTS = ("stomach", "colon")
LUNG_PROMPTS = ("left lung", "right lung")
COMPONENT_STRUCTURE = ndimage.generate_binary_structure(3, 3)


def dice_coefficient(a: np.ndarray, b: np.ndarray) -> float:
    """Dice for binary arrays; two empty masks have Dice 1."""
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    if a.shape != b.shape:
        raise ValueError(f"Dice shape mismatch: {a.shape} != {b.shape}")
    na, nb = int(a.sum()), int(b.sum())
    if na + nb == 0:
        return 1.0
    return 2.0 * int(np.count_nonzero(a & b)) / (na + nb)


def resample_mask_to_reference(
    mask: np.ndarray, source_affine: np.ndarray, reference: nib.spatialimages.SpatialImage
) -> tuple[np.ndarray, bool]:
    """Return a nearest-neighbor mask on reference grid and whether resampling occurred."""
    mask = np.asarray(mask, dtype=np.uint8)
    ref_shape = tuple(int(v) for v in reference.shape[:3])
    same_grid = mask.shape == ref_shape and np.allclose(
        source_affine, reference.affine, rtol=0.0, atol=1e-4
    )
    if same_grid:
        return mask.astype(bool), False
    src = nib.Nifti1Image(mask, source_affine)
    aligned = resample_from_to(src, (ref_shape, reference.affine), order=0)
    return (np.asanyarray(aligned.dataobj) > 0), True


def canonical_image(path: Path) -> nib.spatialimages.SpatialImage:
    return nib.as_closest_canonical(nib.load(str(path)))


def image_mask(img: nib.spatialimages.SpatialImage) -> np.ndarray:
    return np.asanyarray(img.dataobj) > 0


def volume_ml(mask: np.ndarray, spacing: tuple[float, float, float]) -> float:
    return int(np.count_nonzero(mask)) * float(np.prod(spacing)) / 1000.0


def component_stats(mask: np.ndarray) -> tuple[int, float]:
    count = int(np.count_nonzero(mask))
    if count == 0:
        return 0, 0.0
    labels, n = ndimage.label(mask, structure=COMPONENT_STRUCTURE)
    sizes = np.bincount(labels.ravel())[1:]
    return int(n), float(sizes.max() / count) if sizes.size else 0.0


def case_ct_path(case_id: str, ct_root: Path) -> Path | None:
    number = int(case_id.rsplit("_", 1)[1])
    candidates = (
        ct_root / "shortlist_38" / case_id / "ct.nii.gz",
        ct_root / str(number) / "ct.nii.gz",
    )
    return next((p for p in candidates if p.is_file()), None)


def selected_case_ids(shortlist: Path) -> list[str]:
    import pandas as pd

    frame = pd.read_csv(shortlist, dtype={"case_id": str})
    if not {"case_id", "organ"}.issubset(frame.columns):
        raise ValueError(f"Shortlist lacks case_id/organ columns: {shortlist}")
    ids = set(frame["case_id"].dropna().astype(str))
    ids.update(EXTRA_CASES)
    return sorted(ids)


def aligned_label(path: Path, target: nib.spatialimages.SpatialImage) -> tuple[np.ndarray, bool]:
    img = canonical_image(path)
    data, changed = resample_mask_to_reference(image_mask(img), img.affine, target)
    return data, changed


def metric_row(
    case_id: str,
    organ: str,
    pred: np.ndarray,
    pred_affine: np.ndarray,
    label_img: nib.spatialimages.SpatialImage,
    label: np.ndarray,
    lung_union: np.ndarray,
    seconds: float,
) -> tuple[dict, np.ndarray, bool]:
    pred_aligned, did_resample = resample_mask_to_reference(pred, pred_affine, label_img)
    spacing = tuple(float(x) for x in label_img.header.get_zooms()[:3])
    n_label, _ = component_stats(label)
    n_pred, largest = component_stats(pred_aligned)
    nv, pv = int(label.sum()), int(pred_aligned.sum())
    intersection = int(np.count_nonzero(label & pred_aligned))
    row = {
        "case_id": case_id,
        "organ": organ,
        "label_volume_ml": volume_ml(label, spacing),
        "pred_volume_ml": volume_ml(pred_aligned, spacing),
        "volume_ratio_pred_over_label": pv / nv if nv else math.nan,
        "dice": dice_coefficient(label, pred_aligned),
        "n_components_label": n_label,
        "n_components_pred": n_pred,
        "largest_component_fraction_pred": largest,
        "pred_inside_label_fraction": intersection / pv if pv else 0.0,
        "label_inside_pred_fraction": intersection / nv if nv else 0.0,
        "pred_overlap_with_label_lung_fraction": (
            int(np.count_nonzero(pred_aligned & lung_union)) / pv if pv else 0.0
        ),
        "seconds": seconds,
        "error": "empty_label" if not nv else ("empty_prediction" if not pv else ""),
        "prediction_resampled_to_label_grid": did_resample,
    }
    return row, pred_aligned, did_resample


def append_row(path: Path, fieldnames: list[str], row: dict) -> None:
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        f.flush()


def append_error(path: Path, case_id: str, stage: str, exc: BaseException) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{case_id}\t{stage}\t{type(exc).__name__}: {exc}\n")
        f.flush()


def output_mask(path: Path, mask: np.ndarray, affine: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = nib.Nifti1Image(mask.astype(np.uint8), affine)
    img.header.set_data_dtype(np.uint8)
    nib.save(img, str(path))


def gpu_peak_mb(torch) -> float:
    if not torch.cuda.is_available():
        return 0.0
    return float(torch.cuda.max_memory_allocated() / (1024 ** 2))


def run(
    shortlist: Path = SHORTLIST_DEFAULT,
    ct_root: Path = CT_ROOT_DEFAULT,
    label_root: Path = LABEL_ROOT_DEFAULT,
    model_dir: Path = MODEL_DEFAULT,
    out_dir: Path = OUT_DEFAULT,
) -> tuple[list[dict], list[dict]]:
    # Import only after the caller has checked/selected the CUDA-capable runtime.
    import torch

    model_dir = model_dir.resolve()
    if not model_dir.is_dir():
        raise FileNotFoundError(f"Model directory missing: {model_dir}")
    sys.path.insert(0, str(model_dir))
    from dart_seg import DartSeg

    ids = selected_case_ids(shortlist)
    print(f"Shortlist used: {shortlist}")
    print(f"Deduplicated case count: {len(ids)}")
    print("Cases: " + ", ".join(ids))
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_root = out_dir / "preds"
    lung_root = out_dir / "lung_diag"
    main_csv = out_dir / "pilot_a_metrics.csv"
    lung_csv = out_dir / "lung_diag.csv"
    errors = out_dir / "errors.log"

    model = DartSeg.from_pretrained(str(model_dir), device="cuda")
    available = set(model.prompts)
    required = set(MAIN_PROMPTS + LUNG_PROMPTS)
    missing_prompts = sorted(required - available)
    if missing_prompts:
        raise ValueError(f"Required prompts absent from model: {missing_prompts}")
    print("Prompts verified: stomach, colon, left lung, right lung")
    print(f"CUDA device: {torch.cuda.get_device_name(0)}")

    main_fields = [
        "case_id", "organ", "label_volume_ml", "pred_volume_ml",
        "volume_ratio_pred_over_label", "dice", "n_components_label",
        "n_components_pred", "largest_component_fraction_pred",
        "pred_inside_label_fraction", "label_inside_pred_fraction",
        "pred_overlap_with_label_lung_fraction", "seconds", "error",
        "prediction_resampled_to_label_grid",
    ]
    lung_fields = [
        "case_id", "lung", "dart_lung_volume_ml", "dice_with_label_lung",
        "dart_lung_inside_label_colon_fraction",
        "label_lung_inside_dart_lung_fraction", "seconds", "error",
        "prediction_resampled_to_label_grid",
    ]
    main_rows: list[dict] = []
    lung_rows: list[dict] = []
    smoke_ids = [c for c in ("PanTS_00000001", "PanTS_00000040", "PanTS_00000170") if c in ids]
    done_main: set[str] = set()

    def process_main_case(case_id: str, smoke: bool = False) -> None:
        ct_path = case_ct_path(case_id, ct_root)
        if ct_path is None:
            raise FileNotFoundError(f"No CT found under {ct_root} for {case_id}")
        start = time.perf_counter()
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        masks, affine = model.predict_file(str(ct_path), list(MAIN_PROMPTS))
        elapsed = time.perf_counter() - start
        peak = gpu_peak_mb(torch)
        case_dir = pred_root / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        rows_case = []
        for organ in MAIN_PROMPTS:
            label_path = label_root / case_id / "segmentations" / f"{organ}.nii.gz"
            lung_paths = [
                label_root / case_id / "segmentations" / "lung_left.nii.gz",
                label_root / case_id / "segmentations" / "lung_right.nii.gz",
            ]
            label_img = canonical_image(label_path)
            label = image_mask(label_img)
            lung_masks = [aligned_label(p, label_img)[0] for p in lung_paths]
            lung_union = lung_masks[0] | lung_masks[1]
            row, aligned_pred, changed = metric_row(
                case_id, organ, masks[organ], affine, label_img, label, lung_union, elapsed
            )
            if changed:
                print(f"RESAMPLED prediction to label grid: {case_id} {organ} (nearest neighbor)")
            out_path = case_dir / f"{organ}.nii.gz"
            output_mask(out_path, aligned_pred, label_img.affine)
            append_row(main_csv, main_fields, row)
            main_rows.append(row)
            rows_case.append(row)
        print(
            f"{'SMOKE ' if smoke else ''}{case_id}: {elapsed:.2f}s; "
            f"CUDA peak allocated {peak:.0f} MiB; "
            + "; ".join(f"{r['organ']} Dice={r['dice']:.4f}" for r in rows_case)
        )
        done_main.add(case_id)
        del masks
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    print("SMOKE TEST")
    for case_id in smoke_ids:
        try:
            process_main_case(case_id, smoke=True)
        except Exception as exc:
            append_error(errors, case_id, "main_smoke", exc)
            print(f"SMOKE FAILURE {case_id}: {type(exc).__name__}: {exc}")
            # Record one error row for each target organ; continue with remaining cases.
            for organ in MAIN_PROMPTS:
                row = {k: "" for k in main_fields}
                row.update(case_id=case_id, organ=organ, seconds=0.0, error=f"{type(exc).__name__}: {exc}")
                append_row(main_csv, main_fields, row)
                main_rows.append(row)
            done_main.add(case_id)

    print("SMOKE RESULTS TABLE")
    for r in main_rows:
        if r["case_id"] in smoke_ids:
            print({k: r.get(k) for k in (
                "case_id", "organ", "label_volume_ml", "pred_volume_ml", "volume_ratio_pred_over_label",
                "dice", "n_components_label", "n_components_pred",
                "largest_component_fraction_pred", "pred_inside_label_fraction",
                "label_inside_pred_fraction", "pred_overlap_with_label_lung_fraction",
                "seconds", "error"
            )})

    print("MAIN RUN")
    for case_id in ids:
        if case_id in done_main:
            continue
        try:
            process_main_case(case_id)
        except Exception as exc:
            append_error(errors, case_id, "main", exc)
            print(f"MAIN FAILURE {case_id}: {type(exc).__name__}: {exc}")
            for organ in MAIN_PROMPTS:
                row = {k: "" for k in main_fields}
                row.update(case_id=case_id, organ=organ, seconds=0.0, error=f"{type(exc).__name__}: {exc}")
                append_row(main_csv, main_fields, row)
                main_rows.append(row)

    print("LUNG DIAGNOSTIC RUN")
    for case_id in EXTRA_CASES:
        ct_path = case_ct_path(case_id, ct_root)
        try:
            if ct_path is None:
                raise FileNotFoundError(f"No CT found for {case_id}")
            start = time.perf_counter()
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
            masks, affine = model.predict_file(str(ct_path), list(LUNG_PROMPTS))
            elapsed = time.perf_counter() - start
            peak = gpu_peak_mb(torch)
            for prompt, key, label_file in (
                ("left lung", "lung_left", "lung_left.nii.gz"),
                ("right lung", "lung_right", "lung_right.nii.gz"),
            ):
                label_path = label_root / case_id / "segmentations" / label_file
                label_img = canonical_image(label_path)
                label = image_mask(label_img)
                pred, changed = resample_mask_to_reference(masks[prompt], affine, label_img)
                if changed:
                    print(f"RESAMPLED lung prediction to label grid: {case_id} {key} (nearest neighbor)")
                output_mask(lung_root / case_id / f"{key}.nii.gz", pred, label_img.affine)
                colon, _ = aligned_label(
                    label_root / case_id / "segmentations" / "colon.nii.gz", label_img
                )
                p_count, l_count = int(pred.sum()), int(label.sum())
                overlap = int(np.count_nonzero(pred & label))
                row = {
                    "case_id": case_id,
                    "lung": key,
                    "dart_lung_volume_ml": volume_ml(pred, tuple(label_img.header.get_zooms()[:3])),
                    "dice_with_label_lung": dice_coefficient(pred, label),
                    "dart_lung_inside_label_colon_fraction": (
                        int(np.count_nonzero(pred & colon)) / p_count if p_count else 0.0
                    ),
                    "label_lung_inside_dart_lung_fraction": overlap / l_count if l_count else 0.0,
                    "seconds": elapsed,
                    "error": "empty_label_lung" if not l_count else ("empty_dart_lung" if not p_count else ""),
                    "prediction_resampled_to_label_grid": changed,
                }
                append_row(lung_csv, lung_fields, row)
                lung_rows.append(row)
            print(f"LUNG {case_id}: {elapsed:.2f}s; CUDA peak allocated {peak:.0f} MiB")
            del masks
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as exc:
            append_error(errors, case_id, "lung_diag", exc)
            print(f"LUNG FAILURE {case_id}: {type(exc).__name__}: {exc}")
            for key in ("lung_left", "lung_right"):
                row = {k: "" for k in lung_fields}
                row.update(case_id=case_id, lung=key, seconds=0.0, error=f"{type(exc).__name__}: {exc}")
                append_row(lung_csv, lung_fields, row)
                lung_rows.append(row)

    print(f"Main metrics: {main_csv}")
    print(f"Lung diagnostic: {lung_csv}")
    print(f"Failures log: {errors}")
    return main_rows, lung_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the DART-Seg Pilot A comparison")
    parser.add_argument("--shortlist", type=Path, default=SHORTLIST_DEFAULT)
    parser.add_argument("--ct-root", type=Path, default=CT_ROOT_DEFAULT)
    parser.add_argument("--labels-root", type=Path, default=LABEL_ROOT_DEFAULT)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()
    import torch

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is unavailable; Pilot A requires CUDA and was not run.")
    run(args.shortlist, args.ct_root, args.labels_root, args.model_dir, args.out)


if __name__ == "__main__":
    main()
