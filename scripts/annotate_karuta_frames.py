"""Draft YOLO bounding boxes for extracted single-card oblique frames.

Uses color mapping (A01 etc) and assigns global 100-card class = card_id - 1.
All labels are provisional: visually inspect previews before using them.
Does NOT modify raw images/videos or the legacy green20 training sets.

Run:
 uv run python scripts/annotate_karuta_frames.py --color blue20 --direction LR
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import cv2
import numpy as np

from auto_annotate import candidate_rects, make_annotation, read_image, save_image

ROOT = Path(__file__).resolve().parents[1]
COLORS = ("green20", "blue20", "pink20", "yellow20", "orange20")
CARD_NAME = re.compile(r"^card_(\d{3})_(LR|FB)_h01_s\d+_f\d{6}\.png$", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--color", choices=COLORS, required=True)
    ap.add_argument("--direction", choices=("LR", "FB"), required=True)
    ap.add_argument("--session", default="s01")
    ap.add_argument("--border-width", type=float, default=.10)
    ap.add_argument("--border-height", type=float, default=.06)
    args = ap.parse_args()
    if not (0 <= args.border_width <= .30 and 0 <= args.border_height <= .30):
        ap.error("Border expansion must be between 0 and 0.30")
    with (ROOT / "data/metadata" / f"{args.color}_cards.csv").open(encoding="utf-8-sig", newline="") as f:
        mapping = list(csv.DictReader(f))
    id_lookup = {int(r["card_id"]): r["group_id"] for r in mapping}
    src = ROOT / "data/raw" / args.color / "train/single/oblique/extracted" / f"h01_{args.session}" / args.direction
    out = ROOT / "data/annotations/video_frames" / args.color / f"h01_{args.session}" / args.direction
    if not src.is_dir():
        ap.error(f"Missing images: {src}")
    images = sorted(src.glob("*.png"))
    if not images:
        ap.error(f"No extracted PNG images in {src}")
    labels = out / "labels"
    previews = out / "previews"
    labels.mkdir(parents=True, exist_ok=True)
    previews.mkdir(parents=True, exist_ok=True)
    rows = []
    for image_path in images:
        m = CARD_NAME.fullmatch(image_path.name)
        result = dict(image=image_path.name, card_id="", group_id="", class_id="",
                      status="", method="", score="", corner_points_px="")
        label_path = labels / f"{image_path.stem}.txt"
        # A previous label can only be replaced through explicit --not-supported;
        # never silently overwrite manually corrected labels.
        if label_path.exists():
            result["status"] = "SKIPPED_EXISTING_LABEL"
            rows.append(result)
            continue
        try:
            if m is None or m.group(2).upper() != args.direction:
                raise ValueError("Unexpected filename/direction")
            cid = int(m.group(1))
            if cid not in id_lookup:
                raise ValueError(f"Card {cid:03d} is not in {args.color} mapping")
            img = read_image(image_path)
            candidates = candidate_rects(img, args.border_width, args.border_height)
            if not candidates:
                raise ValueError("No contour candidate found")
            score, corners, method = candidates[0]
            xywh = make_annotation(img, corners)
            if xywh is None:
                raise ValueError("Invalid outer bounding box")
            # Keep the class numbering GLOBAL; do not reuse green20 class 0..19.
            class_id = cid - 1
            result.update(card_id=f"{cid:03d}", group_id=id_lookup[cid], class_id=class_id,
                          status="REVIEW", method=method, score=f"{score:.4f}",
                          corner_points_px=";".join(f"{x:.1f},{y:.1f}" for x,y in corners))
            vis = img.copy()
            cv2.polylines(vis, [corners.astype(np.int32)], True, (0,165,255), 3)
            h,w = vis.shape[:2]
            cx,cy,bw,bh = xywh
            x0,y0 = int((cx-bw/2)*w), int((cy-bh/2)*h)
            x1,y1 = int((cx+bw/2)*w), int((cy+bh/2)*h)
            cv2.rectangle(vis,(x0,y0),(x1,y1),(255,210,0),2)
            cv2.putText(vis,f"{id_lookup[cid]} / {cid:03d} / class {class_id} / REVIEW",
                        (12,35),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,0,255),2)
            scale = min(1., 1100 / max(h,w))
            if scale < 1:
                vis = cv2.resize(vis,(round(w*scale),round(h*scale)))
            save_image(previews / f"{image_path.stem}.jpg", vis)
            # Write only after a preview is available, to avoid orphan labels.
            label_path.write_text(f"{class_id} " + " ".join(f"{v:.6f}" for v in xywh) + "\n",
                                  encoding="utf-8")
        except (ValueError,OSError,cv2.error) as exc:
            result["status"] = "FAIL: " + str(exc)
        rows.append(result)
        print(f"{image_path.name}: {result['status']}")
    report = out / "annotation_report.csv"
    with report.open("w", encoding="utf-8-sig", newline="") as file:
        fields = ("image","card_id","group_id","class_id","status","method","score","corner_points_px")
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Labels: {labels}\nPreviews: {previews}\nReport: {report}")
    print("DO NOT train directly from REVIEW labels; confirm and correct every bounding box first.")


if __name__ == "__main__":
    main()
