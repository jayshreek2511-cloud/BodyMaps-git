"""Label-only morphology and surface-contact features."""
import numpy as np
from scipy import ndimage

from config import LABEL_IDS, SMALL_FRAGMENT_ML

_NEIGHBORS = ("liver", "spleen", "kidney_left", "kidney_right", "pancreas", "duodenum")


def _bbox(mask):
    coords = np.where(mask)
    return tuple((int(v.min()), int(v.max()) + 1) for v in coords) if coords[0].size else None


def extract_features(label_volume, organ_id, spacing, all_labels_volume,
                     label_ids=None, organ_mask=None):
    """Compute features from an organ mask and a combined neighbor-label volume."""
    volume = np.asarray(label_volume)
    allv = np.asarray(all_labels_volume)
    label_ids = LABEL_IDS if label_ids is None else label_ids
    mask = volume == int(organ_id) if organ_mask is None else np.asarray(organ_mask, dtype=bool)
    if mask.shape != allv.shape or volume.shape != allv.shape:
        raise ValueError("organ and combined volumes must have matching shapes")
    spacing = tuple(float(v) for v in spacing)
    vox_ml = float(np.prod(spacing)) / 1000.0
    n = int(mask.sum())
    combined_count = int(np.count_nonzero(allv == int(organ_id)))
    out = {"volume_ml": n * vox_ml, "bbox_x_mm": 0.0, "bbox_y_mm": 0.0,
           "bbox_z_mm": 0.0, "bbox_fill_ratio": 0.0, "n_components": 0,
           "largest_component_fraction": 0.0, "n_small_fragments": 0,
           "fragment_volume_fraction": 0.0, "overlap_other_labels_fraction": 0.0,
           "overlap_top1_label": 0, "overlap_top1_fraction": 0.0, "overlap_top2_label": 0, "overlap_top2_fraction": 0.0, "combined_vs_separate_ratio": 0.0}
    for axis in "xyz":
        for side in ("min", "max"):
            out[f"touches_scan_edge_{axis}_{side}"] = False
    out.update({"any_edge_touch": False, "centroid_x_mm": 0.0, "centroid_y_mm": 0.0,
        "centroid_z_mm": 0.0, "centroid_rel_x": 0.0, "centroid_rel_y": 0.0,
        "centroid_rel_z": 0.0, "left_right_side": "unknown", "holes_fraction": 0.0,
        "surface_area_mm2": 0.0, "compactness": 0.0, "z_extent_mm": 0.0,
        "z_extent_fraction_total_labeled": 0.0})
    for name in (*_NEIGHBORS, "other_pair_organ", "background"):
        out[f"contact_{name}_fraction"] = 0.0
    if n == 0:
        return out

    overlap_values = allv[mask]
    overlap_values = overlap_values[(overlap_values != 0) & (overlap_values != int(organ_id))]
    if overlap_values.size:
        values, counts = np.unique(overlap_values, return_counts=True)
        order = np.argsort(-counts, kind="stable")
        out["overlap_top1_label"] = int(values[order[0]])
        out["overlap_top1_fraction"] = float(counts[order[0]] / n)
        if len(order) > 1:
            out["overlap_top2_label"] = int(values[order[1]])
            out["overlap_top2_fraction"] = float(counts[order[1]] / n)
    out["overlap_other_labels_fraction"] = float(overlap_values.size / n)
    out["combined_vs_separate_ratio"] = float(combined_count / n)
    components, count = ndimage.label(mask, structure=np.ones((3, 3, 3), bool))
    sizes = np.bincount(components.ravel())[1:]
    out["n_components"] = int(count)
    out["largest_component_fraction"] = float(sizes.max() / n)
    tiny = sizes[sizes * vox_ml < SMALL_FRAGMENT_ML]
    out["n_small_fragments"] = int(tiny.size)
    out["fragment_volume_fraction"] = float(tiny.sum() / n)

    box, allbox = _bbox(mask), _bbox(allv != 0)
    lengths = [box[i][1] - box[i][0] for i in range(3)]
    dims = [lengths[i] * spacing[i] for i in range(3)]
    for i, axis in enumerate("xyz"):
        out[f"bbox_{axis}_mm"] = float(dims[i])
        out[f"touches_scan_edge_{axis}_min"] = box[i][0] == 0
        out[f"touches_scan_edge_{axis}_max"] = box[i][1] == volume.shape[i]
    out["any_edge_touch"] = any(v for k, v in out.items() if k.startswith("touches_scan_edge_"))
    out["bbox_fill_ratio"] = float(n / np.prod(lengths))
    out["z_extent_mm"] = float(dims[2])
    coords = np.argwhere(mask)
    center = coords.mean(axis=0)
    for i, axis in enumerate("xyz"):
        out[f"centroid_{axis}_mm"] = float(center[i] * spacing[i])
        if allbox:
            allsize = allbox[i][1] - allbox[i][0]
            out[f"centroid_rel_{axis}"] = float(np.clip((center[i] - allbox[i][0]) / max(allsize - 1, 1), 0, 1))
    if allbox:
        mid = (allbox[0][0] + allbox[0][1] - 1) / 2
        out["left_right_side"] = "left" if center[0] < mid else "right"
        out["z_extent_fraction_total_labeled"] = float(lengths[2] / max(allbox[2][1] - allbox[2][0], 1))
    out["holes_fraction"] = float((ndimage.binary_fill_holes(mask).sum() - n) / n)

    face_areas = (spacing[1] * spacing[2], spacing[0] * spacing[2], spacing[0] * spacing[1])
    pair = "colon" if int(organ_id) == label_ids["stomach"] else "stomach"
    names = (*_NEIGHBORS, pair)
    ids = {name: label_ids[name] for name in names}
    contact, surface = {}, 0.0
    for axis in range(3):
        for direction in (-1, 1):
            shift = 1 if direction < 0 else -1
            organ_neighbor = np.roll(mask, shift, axis)
            label_neighbor = np.roll(allv.astype(np.int32), shift, axis)
            edge = [slice(None)] * 3
            edge[axis] = 0 if direction < 0 else -1
            organ_neighbor[tuple(edge)] = False
            label_neighbor[tuple(edge)] = 0
            exposed = mask & ~organ_neighbor
            area = face_areas[axis]
            surface += int(exposed.sum()) * area
            for name, label_id in ids.items():
                contact[name] = contact.get(name, 0.0) + int((exposed & (label_neighbor == label_id)).sum()) * area
            contact["background"] = contact.get("background", 0.0) + int((exposed & (label_neighbor == 0)).sum()) * area
    out["surface_area_mm2"] = float(surface)
    volume_mm3 = n * float(np.prod(spacing))
    out["compactness"] = float(surface ** 3 / (36 * np.pi * volume_mm3 ** 2))
    for name in names:
        key = "other_pair_organ" if name == pair else name
        out[f"contact_{key}_fraction"] = float(contact.get(name, 0) / surface)
    out["contact_background_fraction"] = float(contact.get("background", 0) / surface)
    return out
