"""NIfTI read helper that returns errors instead of raising them."""
from pathlib import Path
import nibabel as nib
import numpy as np


def load_nifti(path):
    """Return (RAS array, voxel spacing mm, error string or None)."""
    try:
        image = nib.as_closest_canonical(nib.load(str(path)))
        array = np.asanyarray(image.dataobj)
        if array.ndim != 3:
            return None, None, f"expected a 3D volume, got {array.ndim}D"
        if not np.isfinite(array).all():
            return None, None, "volume contains non-finite values"
        if array.min(initial=0) >= 0 and array.max(initial=0) <= 255:
            array = array.astype(np.uint8, copy=False)
        else:
            array = array.astype(np.int16, copy=False)
        spacing = tuple(float(v) for v in image.header.get_zooms()[:3])
        if any(not np.isfinite(v) or v <= 0 for v in spacing):
            return None, None, "invalid voxel spacing"
        return array, spacing, None
    except Exception as exc:
        return None, None, f"{Path(path).name}: {type(exc).__name__}: {exc}"
