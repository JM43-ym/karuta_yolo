"""Detect one card per original image, export YOLO labels and visual previews.

Run: uv run python scripts/auto_annotate.py
Images stay unchanged. Inspect previews before using any labels for training.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data/raw/green20/top/h01"
OUTPUT_DIR = ROOT / "data/annotations/green20_h01"
CARD_MAP = ROOT / "data/metadata/green20_cards.csv"
FILENAME_PATTERN = re.compile(r"^card_(\d{3})_top_h\d{2}_s\d{2}\.(png|jpg|jpeg)$", re.I)


def read_image(path: Path) -> np.ndarray:
    # imdecode supports Unicode file paths on Windows.
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot decode: {path}")
    return image


def save_image(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise ValueError(f"Cannot encode image: {path}")
    encoded.tofile(str(path))


def candidate_rects(image: np.ndarray) -> list[tuple[float, np.ndarray, str]]:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Green border cue, broad range to tolerate camera white balance.
    green = cv2.inRange(hsv, (30, 35, 20), (95, 255, 255))
    bright = cv2.inRange(gray, 65, 255)
    masks = [("otsu", otsu), ("bright", bright), ("green", green)]
    proposals: list[tuple[float, np.ndarray, str]] = []
    kernel_size = max(3, round(min(height, width) * 0.012))
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))

    for method, mask in masks:
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:12]:
            contour_area = cv2.contourArea(contour)
            rect = cv2.minAreaRect(contour)
            (cx, cy), (rw, rh), _ = rect
            box_area = rw * rh
            ratio = max(rw, rh) / max(1.0, min(rw, rh))
            fraction = box_area / (width * height)
            fill = contour_area / max(1.0, box_area)
            if not (0.002 <= fraction <= 0.85 and 1.15 <= ratio <= 2.3 and fill >= 0.48):
                continue
            corners = cv2.boxPoints(rect).astype(np.float32)
            # Penalize truncation by image boundaries.
            edge = min(cx, cy, width - cx, height - cy)
            score = (min(fill, 1) * 1.5 + min(fraction, 0.25) * 1.5
                     - 0.5 * (edge < min(width, height) * 0.012))
            proposals.append((score, corners, method))
    return sorted(proposals, key=lambda item: item[0], reverse=True)


def make_annotation(image: np.ndarray, corners: np.ndarray) -> tuple[float, float, float, float] | None:
    h, w = image.shape[:2]
    xs = corners[:, 0]
    ys = corners[:, 1]
    x0, y0 = float(np.min(xs)), float(np.min(ys))
    x1, y1 = float(np.max(xs)), float(np.max(ys))
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(float(w), x1), min(float(h), y1)
    if x1 <= x0 or y1 <= y0:
        return None
    return ((x0 + x1) / (2 * w), (y0 + y1) / (2 * h),
            (x1 - x0) / w, (y1 - y0) / h)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    if not args.input.is_dir():
        parser.error(f"Input folder not found: {args.input}")
    labels_dir = args.output / "labels"
    previews_dir = args.output / "previews"
    labels_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)

    with CARD_MAP.open(encoding="utf-8-sig", newline="") as file:
        records = list(csv.DictReader(file))
    id_to_class = {int(r["card_id"]): idx for idx, r in enumerate(records)}
    paths = sorted((p for p in args.input.iterdir()
                    if p.suffix.lower() in {".png", ".jpg", ".jpeg"}))
    rows = []
    for path in paths:
        match = FILENAME_PATTERN.fullmatch(path.name)
        card_id = int(match.group(1)) if match else None
        result = {"filename": path.name, "card_id": card_id, "class_id": "",
                  "status": "", "method": "", "score": "", "image_width": "",
                  "image_height": "", "corner_points_px": ""}
        label_file = labels_dir / (path.stem + ".txt")
        # Prevent stale labels when an image fails on a subsequent run.
        label_file.unlink(missing_ok=True)
        try:
            image = read_image(path)
            h, w = image.shape[:2]
            result.update(image_width=w, image_height=h)
            if card_id not in id_to_class:
                raise ValueError("Filename has no known green20 card ID")
            candidates = candidate_rects(image)
            if not candidates:
                raise ValueError("No plausible rectangular card detected")
            score, corners, method = candidates[0]
            xywh = make_annotation(image, corners)
            if xywh is None:
                raise ValueError("Invalid bounding rectangle")
            class_id = id_to_class[card_id]
            label_file.write_text(
                f"{class_id} " + " ".join(f"{n:.6f}" for n in xywh) + "\n",
                encoding="utf-8",
            )
            result.update(class_id=class_id, status="REVIEW", method=method,
                          score=round(score, 4),
                          corner_points_px=";".join(f"{x:.1f},{y:.1f}" for x, y in corners))
            vis = image.copy()
            cv2.polylines(vis, [corners.astype(np.int32)], True, (0, 165, 255), 3)
            x0 = int((xywh[0] - xywh[2] / 2) * w)
            y0 = int((xywh[1] - xywh[3] / 2) * h)
            x1 = int((xywh[0] + xywh[2] / 2) * w)
            y1 = int((xywh[1] + xywh[3] / 2) * h)
            cv2.rectangle(vis, (x0, y0), (x1, y1), (255, 200, 0), 2)
            cv2.putText(vis, f"Card {card_id:03d} | REVIEW | {method}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 255), 2)
            # Downscale previews only, leaving original and labels at full resolution.
            scale = min(1.0, 1100 / max(h, w))
            if scale < 1:
                vis = cv2.resize(vis, (round(w * scale), round(h * scale)))
            save_image(previews_dir / (path.stem + ".jpg"), vis)
        except (ValueError, cv2.error, OSError) as exc:
            result.update(status=f"FAIL: {exc}")
        rows.append(result)
        print(f"{path.name}: {result['status']}")

    report = args.output / "report.csv"
    with report.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else
                                ["filename", "card_id", "status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nReport: {report}")
    print(f"Previews: {previews_dir}")
    print("All generated labels are provisional. VISUALLY CHECK every preview.")
    print("Do not train until the review and independent train/val/test split are complete.")


if __name__ == "__main__":
    main()
