import csv
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np

from run_stage0 import main
from config import LABEL_IDS


def test_flat_layout_separate_source_and_combined_option():
    qa_dir = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(dir=qa_dir) as temporary:
        root = Path(temporary)
        case_dir = root / "PanTS_00000001"
        (case_dir / "segmentations").mkdir(parents=True)
        volume = np.zeros((32, 32, 32), dtype=np.uint8)
        volume[3:18, 3:18, 3:18] = LABEL_IDS["stomach"]
        volume[20:29, 20:29, 20:29] = LABEL_IDS["colon"]
        volume[18, 18, 18] = 14
        affine = np.diag([0.7, 0.8, 2.5, 1.0])
        nib.save(nib.Nifti1Image(volume, affine), case_dir / "combined_labels.nii.gz")
        stomach = volume == LABEL_IDS["stomach"]
        stomach[18, 18, 18] = True
        colon = volume == LABEL_IDS["colon"]
        nib.save(nib.Nifti1Image(stomach.astype(np.uint8), affine),
                 case_dir / "segmentations" / "stomach.nii.gz")
        nib.save(nib.Nifti1Image(colon.astype(np.uint8), affine),
                 case_dir / "segmentations" / "colon.nii.gz")
        output = root / "features.csv"
        main(["--root", str(root), "--layout", "flat", "--out", str(output)])
        with output.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        assert len(rows) == 2
        by_organ = {row["organ"]: row for row in rows}
        assert set(by_organ) == {"stomach", "colon"}
        for row in rows:
            assert (row["shape_x"], row["shape_y"], row["shape_z"]) == ("32", "32", "32")
            assert np.isclose(float(row["spacing_x"]), 0.7)
            assert np.isclose(float(row["spacing_y"]), 0.8)
            assert np.isclose(float(row["spacing_z"]), 2.5)
            assert "0" in row["label_ids_present"].split(",")
        assert float(by_organ["stomach"]["overlap_other_labels_fraction"]) > 0
        assert float(by_organ["stomach"]["combined_vs_separate_ratio"]) < 1
        assert float(by_organ["colon"]["combined_vs_separate_ratio"]) == 1
        assert float(by_organ["colon"]["overlap_other_labels_fraction"]) == 0

        combined_out = root / "combined.csv"
        main(["--root", str(root), "--layout", "flat", "--source", "combined",
              "--out", str(combined_out)])
        with combined_out.open(newline="", encoding="utf-8") as source:
            combined_rows = list(csv.DictReader(source))
        assert all(float(row["combined_vs_separate_ratio"]) == 1 for row in combined_rows)
        assert all(float(row["overlap_other_labels_fraction"]) == 0 for row in combined_rows)
