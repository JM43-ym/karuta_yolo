"""Extract distinct, sharp frames from recorded LR/FB card videos.

Run:
 uv run python scripts/extract_karuta_frames.py --color blue20 --direction LR
 uv run python scripts/extract_karuta_frames.py --color blue20 --direction FB --per-video 5

The source videos stay unchanged. Outputs are placed in extracted/h01_s01/LR or FB.
Each output has an explicit card_id from the color mapping CSV. Inspect before training.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COLORS = ("green20", "blue20", "pink20", "yellow20", "orange20")
PATTERN = re.compile(r"^karuta_(\d{1,2})_(LR|FB)\.avi$", re.I)
FIELDS = ("image", "video", "group_id", "card_id", "direction", "frame_index",
          "frame_time_seconds", "sharpness", "selected_position", "note")


def load_mapping(color):
    with (ROOT / "data/metadata" / f"{color}_cards.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if len(rows) != 20:
        raise ValueError(f"{color} must contain 20 card rows")
    return rows


def sharpness(img: np.ndarray) -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (min(gray.shape[1], 640), min(gray.shape[0], 480)))
    return float(cv2.Laplacian(small, cv2.CV_64F).var())


def card_candidate(img):
    # Reuses the existing white-face / outer-border estimate.
    from auto_annotate import candidate_rects
    try:
        candidates = candidate_rects(img, 0.10, 0.06)
        if not candidates:
            return False
        c = candidates[0][1]
        h, w = img.shape[:2]
        cx, cy = c.mean(axis=0)
        return bool(.06*w < cx < .94*w and .06*h < cy < .94*h)
    except (cv2.error, ValueError):
        return False


def select_frames(path: Path, wanted: int, sample_every: int, edge_fraction: float):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if math.isfinite(fps) and fps > 0 else 15.0
    samples = []
    idx = 0
    try:
        while True:
            ok, img = cap.read()
            if not ok:
                break
            if idx % sample_every == 0:
                samples.append((idx, sharpness(img), img))
            idx += 1
    finally:
        cap.release()
    if not samples:
        return [], fps

    n = len(samples)
    # Skip initial and final motion/setup footage when possible.
    a = int(n * edge_fraction)
    b = max(a + 1, int(n * (1 - edge_fraction)))
    usable = samples[a:b]
    # Time bins ensure viewpoints across the sweep; sharpness ranks within each bin.
    result = []
    for j in range(min(wanted, len(usable))):
        begin = j * len(usable) // wanted
        end = max(begin + 1, (j + 1) * len(usable) // wanted)
        subset = usable[begin:end]
        eligible = [s for s in subset if card_candidate(s[2])]
        best = max(eligible or subset, key=lambda s: s[1])
        result.append((best, j))
    result.sort(key=lambda x: x[0][0])
    return result, fps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--color", choices=COLORS, required=True)
    ap.add_argument("--direction", choices=("LR", "FB"), required=True)
    ap.add_argument("--session", default="s01")
    ap.add_argument("--per-video", type=int, default=5)
    ap.add_argument("--sample-every", type=int, default=3)
    ap.add_argument("--edge-fraction", type=float, default=.05)
    args = ap.parse_args()
    if args.per_video < 1 or args.sample_every < 1 or not 0 <= args.edge_fraction < .4:
        ap.error("Invalid sampling arguments")

    source = (ROOT / "data/raw" / args.color / "train/single/oblique/videos" /
              f"h01_{args.session}" / args.direction)
    dest = (ROOT / "data/raw" / args.color / "train/single/oblique/extracted" /
            f"h01_{args.session}" / args.direction)
    if not source.is_dir():
        ap.error(f"No videos folder: {source}")
    videos = sorted(p for p in source.iterdir() if PATTERN.fullmatch(p.name))
    if not videos:
        ap.error(f"No matching karuta_N_{args.direction}.avi files in {source}")
    dest.mkdir(parents=True, exist_ok=True)
    mapping = load_mapping(args.color)
    report = dest / "extraction_report.csv"
    prior = []
    if report.exists():
        with report.open(encoding="utf-8-sig", newline="") as f:
            prior = list(csv.DictReader(f))
    new_rows = []
    for video in videos:
        m = PATTERN.fullmatch(video.name)
        num = int(m.group(1))
        direction = m.group(2).upper()
        if not 1 <= num <= 20 or direction != args.direction:
            continue
        row = mapping[num-1]
        extracted, fps = select_frames(video, args.per_video, args.sample_every, args.edge_fraction)
        if not extracted:
            print(f"WARNING: no frames: {video}")
            continue
        # First inspect all potential output paths, to avoid partial overwrites.
        outputs = [(dest / f"card_{int(row['card_id']):03d}_{direction}_h01_{args.session}_f{item[0][0]:06d}.png",
                    item) for item in extracted]
        if any(out.exists() for out, _ in outputs):
            print(f"SKIP {video.name}: extracted frame(s) already exist. No overwrite.")
            continue
        for out, ((frame_idx, score, frame), position) in outputs:
            ok, encoded = cv2.imencode(".png", frame)
            if not ok:
                raise RuntimeError(f"PNG encoding failed: {out}")
            encoded.tofile(str(out))
            new_rows.append(dict(image=out.name, video=video.name,
                                 group_id=row["group_id"], card_id=row["card_id"],
                                 direction=direction, frame_index=frame_idx,
                                 frame_time_seconds=f"{frame_idx / fps:.3f}",
                                 sharpness=f"{score:.2f}", selected_position=position+1,
                                 note="REVIEW angle/blur/whole card manually"))
        print(f"{video.name} -> {len(outputs)} frames")
    if new_rows:
        names = {r["image"] for r in new_rows}
        rows = [r for r in prior if r.get("image") not in names] + new_rows
        with report.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved {len(new_rows)} new images; report: {report}")
    else:
        print("No new images written (existing output is protected).")
    print("IMPORTANT: time bins do NOT guarantee exact physical angles; inspect all output frames.")


if __name__ == "__main__":
    main()
