"""Class-agnostic deduplication of overlapping YOLO boxes.

Suppress predictions that cover the same physical card, regardless of predicted
class, then cap the result count. This cannot guarantee one box per real card:
non-overlapping duplicates and false positives can remain.
"""
from __future__ import annotations


def overlap_metrics(a, b):
    ax0, ay0, ax1, ay1 = map(float, a)
    bx0, by0, bx1, by1 = map(float, b)
    intersection = max(0.0, min(ax1, bx1) - max(ax0, bx0)) * max(
        0.0, min(ay1, by1) - max(ay0, by0)
    )
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    union = area_a + area_b - intersection
    iou = intersection / union if union > 0 else 0.0
    cover = intersection / min(area_a, area_b) if min(area_a, area_b) > 0 else 0.0
    return iou, cover


def select_indices(boxes, scores, *, max_cards=20, iou_threshold=0.55,
                   coverage_threshold=0.80):
    """Return indices ordered by confidence (descending).

    Two boxes are considered duplicate if their IoU OR coverage of the smaller
    box exceeds the corresponding threshold. Predicted classes are ignored.
    """
    if len(boxes) != len(scores):
        raise ValueError("Boxes and scores must have equal lengths")
    if max_cards < 1 or not (0 < iou_threshold < 1) or not (0 < coverage_threshold <= 1):
        raise ValueError("Invalid postprocessing thresholds")
    selected = []
    for index in sorted(range(len(boxes)), key=lambda i: (-float(scores[i]), i)):
        if any(
            (lambda iou, coverage: iou >= iou_threshold or
             coverage >= coverage_threshold)(*overlap_metrics(boxes[index], boxes[kept]))
            for kept in selected
        ):
            continue
        selected.append(index)
        if len(selected) == max_cards:
            break
    return selected
