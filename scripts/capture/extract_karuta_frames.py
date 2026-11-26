"""Extract viewpoint-diverse and sharp frames, irrespective of camera sweep speed.

Two-pass algorithm:
  1) Read sampled frames and calculate cumulative visual change in a central region.
  2) Choose sharp frames near evenly spaced *visual-change* progress points.
  3) Re-read and save only the chosen original-resolution frames.

The path-progress approach is independent of clip duration or fps. It does not
measure physical viewing angle, and all selected frames require visual review.

Usage:
  uv run --no-sync python scripts/extract_karuta_frames.py --color green20 --direction LR
  uv run --no-sync python scripts/extract_karuta_frames.py --color green20 --direction FB --per-video 7

By default existing extracted images are never overwritten. Use --replace to
deliberately regenerate *only* the selected color/direction/session's outputs,
after reviewing the reported paths and backing up manual changes.
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_SCRIPTS_DIR = _Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS_DIR))


import argparse
import csv
import math
import re
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
COLORS = ("green20", "blue20", "pink20", "yellow20", "orange20")
PATTERN = re.compile(r"^karuta_(\d{1,2})_(LR|FB)\.avi$", re.I)
OUTPUT_PATTERN = re.compile(r"^card_(\d{3})_(LR|FB)_h01_(s\d+)_f\d{6}\.png$", re.I)
FIELDS = ("image", "video", "group_id", "card_id", "direction", "frame_index",
          "frame_time_seconds", "sharpness", "motion_progress", "selection_method",
          "selected_position", "note")


def load_mapping(color: str):
    with (ROOT / "data/metadata" / f"{color}_cards.csv").open(encoding="utf-8-sig", newline="") as f:
        cards = list(csv.DictReader(f))
    if len(cards) != 20:
        raise ValueError(f"Expected 20 records for {color}")
    # Video index karuta_01 == color-group A01/B01/etc., NOT first CSV row.
    cards.sort(key=lambda card: card["group_id"])
    return cards


def describe(img: np.ndarray):
    h, w = img.shape[:2]
    # Focus on the card's vicinity, rather than background changes at frame edges.
    roi = img[int(h*.12):int(h*.88), int(w*.18):int(w*.82)]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    descriptor = cv2.resize(cv2.GaussianBlur(gray, (5, 5), 0), (64, 64),
                            interpolation=cv2.INTER_AREA).astype(np.float32)
    crisp = cv2.resize(gray, (min(640, gray.shape[1]), min(480, gray.shape[0])),
                       interpolation=cv2.INTER_AREA)
    focus = float(cv2.Laplacian(crisp, cv2.CV_64F).var())
    return descriptor, focus


def scan_video(path: Path, sample_every: int):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Unable to open AVI: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if not math.isfinite(fps) or fps <= 0:
        fps = 15.0
    descriptors, scores, indices = [], [], []
    n = 0
    try:
        while True:
            ok, img = cap.read()
            if not ok:
                break
            if n % sample_every == 0:
                desc, focus = describe(img)
                descriptors.append(desc)
                scores.append(focus)
                indices.append(n)
            n += 1
    finally:
        cap.release()
    if not indices:
        return np.array([], dtype=int), np.array([], dtype=float), np.array([], dtype=float), fps

    # Mean grayscale differences give an approximate traversal of the visual
    # sweep. Median filtering damps compression/noise and small hand jitters.
    diffs = np.array([
        float(np.abs(a-b).mean()) for a,b in zip(descriptors[:-1], descriptors[1:])
    ], dtype=np.float64)
    if len(diffs) >= 5:
        smooth = np.convolve(np.pad(diffs, (2,2), mode="edge"),
                             np.ones(5)/5., mode="valid")
    else:
        smooth = diffs.copy()
    # Remove a small per-video jitter floor, otherwise still segments dominate.
    floor = float(np.quantile(smooth, .15)) if len(smooth) else 0.
    motion = np.maximum(smooth - floor, 0.)
    progress = np.r_[0., np.cumsum(motion)]
    if progress[-1] > 1e-8:
        progress /= progress[-1]
    else:
        progress = np.linspace(0., 1., len(indices))
    return np.array(indices, dtype=int), np.array(scores), progress, fps


def choose(indices, scores, progress, wanted: int, trim: float):
    if not len(indices):
        return []
    start = int(len(indices) * trim)
    stop = max(start+1, len(indices)-int(len(indices)*trim))
    idx = np.arange(start, stop)
    if not len(idx):
        return []

    # Select sharp frames around uniformly distributed visual-change fractions.
    # A frame is never chosen twice. More recording time spent at a single
    # viewpoint does not yield more samples from that viewpoint.
    usable_progress = progress[idx]
    left, right = float(usable_progress[0]), float(usable_progress[-1])
    targets = np.linspace(left, right, min(wanted,len(idx)))
    selected = []
    remaining = set(int(k) for k in idx)
    for target in targets:
        if not remaining:
            break
        ordered = sorted(remaining, key=lambda k: abs(float(progress[k])-target))
        neighborhood = ordered[:max(5, math.ceil(len(idx)/max(wanted,1)*1.5))]
        spread = max((right-left)/max(wanted-1,1), .03)
        # Sharpness has different absolute ranges depending on camera exposure;
        # rank it relative to *this video*, not other videos.
        scale = max(float(np.quantile(scores[idx], .90)), 1.)
        best = max(neighborhood,
                   key=lambda k: (.60*min(float(scores[k])/scale, 2.)
                                  -.95*abs(float(progress[k])-target)/spread))
        selected.append(best)
        remaining.remove(best)
    return sorted(selected, key=lambda k: int(indices[k]))


def choose_near_front(indices, scores, progress, wanted: int, front_progress: float,
                      sweep_half_angle: float, max_angle: float, trim: float):
    """Choose sharp diverse frames in a *nominal* front-facing window.

    Assumes cumulative visual progress is monotonic and linear with angle.
    This is NOT calibrated physical angle; review every extracted image.
    """
    if not len(indices):
        return []
    lower = max(0.0, front_progress - max_angle / (2.0 * sweep_half_angle))
    upper = min(1.0, front_progress + max_angle / (2.0 * sweep_half_angle))
    start = int(len(indices) * trim)
    stop = max(start + 1, len(indices) - int(len(indices) * trim))
    candidates = [int(k) for k in range(start, stop)
                  if lower <= float(progress[k]) <= upper]
    if len(candidates) < wanted:
        raise ValueError(f"Only {len(candidates)} candidate frames in estimated front window; "
                         f"need {wanted}. Check front-progress, sweep angle, or sampling.")
    targets = np.linspace(lower, upper, wanted + 2)[1:-1]
    remaining = set(candidates)
    selected = []
    sharp_scale = max(float(np.quantile(scores[candidates], .90)), 1.0)
    span = max((upper - lower) / max(wanted, 1), .005)
    for target in targets:
        ranked = sorted(remaining, key=lambda k: abs(float(progress[k]) - target))
        near = ranked[:max(5, math.ceil(len(candidates) / wanted * 1.5))]
        chosen = max(near, key=lambda k: (.60 * min(float(scores[k]) / sharp_scale, 2.0)
                                            - .95 * abs(float(progress[k]) - target) / span))
        selected.append(chosen)
        remaining.remove(chosen)
    return sorted(selected, key=lambda k: int(indices[k]))


def read_selected(path: Path, indices: list[int]):
    wanted = set(indices)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Unable to reopen AVI: {path}")
    frames = {}
    i = 0
    try:
        while wanted:
            ok, frame = cap.read()
            if not ok:
                break
            if i in wanted:
                frames[i] = frame
                wanted.remove(i)
            i += 1
    finally:
        cap.release()
    if wanted:
        raise ValueError(f"Could not decode selected frames: {sorted(wanted)}")
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--color", choices=COLORS, required=True)
    ap.add_argument("--direction", choices=("LR","FB"), required=True)
    ap.add_argument("--session", default="s01")
    ap.add_argument("--per-video", type=int, default=5)
    ap.add_argument("--sample-every", type=int, default=1,
                    help="Analyze every Nth frame (default 1; fastest sweeps benefit from 1)")
    ap.add_argument("--edge-fraction", type=float, default=.03)
    ap.add_argument("--selection", choices=("diverse", "near-front"), default="diverse",
                    help="near-front limits selection to an approximate frontal window")
    ap.add_argument("--front-progress", type=float, default=.5,
                    help="Estimated frontal viewpoint in cumulative motion progress (default 0.5)")
    ap.add_argument("--sweep-half-angle", type=float, default=None,
                    help="Approximate physical half sweep, degrees; required with near-front")
    ap.add_argument("--max-angle", type=float, default=15.,
                    help="Desired angular distance from frontal view (default 15 degrees; estimated only)")
    ap.add_argument("--output-subdir", type=str, default=None,
                    help="New subfolder under extracted/.../LR or FB; avoids touching old data")
    ap.add_argument("--replace", action="store_true",
                    help="Replace extracted PNGs for each matching video. WARNING: old labels may no longer match.")
    args = ap.parse_args()
    if args.per_video < 1 or args.sample_every < 1 or not 0 <= args.edge_fraction < .4:
        ap.error("Invalid sampling configuration")
    if args.selection == "near-front":
        if args.sweep_half_angle is None or args.sweep_half_angle <= args.max_angle or args.max_angle <= 0:
            ap.error("--selection near-front requires --sweep-half-angle greater than --max-angle (>0)")
        if not 0 < args.front_progress < 1:
            ap.error("--front-progress must be between 0 and 1")
        if args.output_subdir is None:
            args.output_subdir = "near_front_15" if args.max_angle == 15 else f"near_front_{args.max_angle:g}"
    if args.output_subdir is not None and (not re.fullmatch(r"[A-Za-z0-9_-]+", args.output_subdir)
                                         or args.output_subdir in (".", "..")):
        ap.error("--output-subdir must contain only letters, numbers, underscores or hyphens")
    if not re.fullmatch(r"s\d+", args.session):
        ap.error("--session must look like s01")

    source = ROOT / "data/raw" / args.color / "train/single/oblique/videos" / f"h01_{args.session}" / args.direction
    dest = ROOT / "data/raw" / args.color / "train/single/oblique/extracted" / f"h01_{args.session}" / args.direction
    if args.output_subdir:
        dest = dest / args.output_subdir
    if not source.is_dir():
        ap.error(f"No video directory: {source}")
    videos = sorted(p for p in source.iterdir() if PATTERN.fullmatch(p.name))
    if not videos:
        ap.error(f"No karuta_N_{args.direction}.avi in {source}")
    dest.mkdir(parents=True, exist_ok=True)
    mapping = load_mapping(args.color)
    report = dest / "extraction_report.csv"
    old_rows = []
    if report.exists():
        with report.open(encoding="utf-8-sig", newline="") as f:
            old_rows = list(csv.DictReader(f))
    appended = []
    for video in videos:
        m = PATTERN.fullmatch(video.name)
        num, direction = int(m.group(1)), m.group(2).upper()
        if not 1 <= num <= 20 or direction != args.direction:
            continue
        card = mapping[num-1]
        cid = int(card["card_id"])
        prefix = f"card_{cid:03d}_{direction}_h01_{args.session}_"
        existing = list(dest.glob(prefix+"f*.png"))
        if existing and not args.replace:
            print(f"SKIP {video.name}: {len(existing)} extracted frames exist (use --replace deliberately)")
            continue
        idx, focus, progress, fps = scan_video(video, args.sample_every)
        if args.selection == "near-front":
            try:
                picks = choose_near_front(idx, focus, progress, args.per_video,
                                          args.front_progress, args.sweep_half_angle,
                                          args.max_angle, args.edge_fraction)
            except ValueError as exc:
                print(f"WARNING {video.name}: {exc}")
                continue
        else:
            picks = choose(idx, focus, progress, args.per_video, args.edge_fraction)
        if not picks:
            print(f"WARNING {video.name}: no frames")
            continue
        selected = [int(idx[i]) for i in picks]
        output_paths = [
            dest / f"{prefix}f{j:06d}.png" for j in selected
        ]
        if any(p.exists() for p in output_paths) and not args.replace:
            print(f"SKIP {video.name}: a target file exists; no overwrite")
            continue
        frames = read_selected(video, selected)
        encoded_images = []
        for j, target in zip(selected, output_paths):
            ok, encoded = cv2.imencode(".png", frames[j])
            if not ok:
                raise RuntimeError(f"Cannot encode {target}")
            encoded_images.append((target,encoded))
        if args.replace:
            # Caution: annotation labels/previews for old extracted files may
            # persist; users must re-review/rebuild them before training.
            for path in existing:
                path.unlink()
        for target, encoded in encoded_images:
            encoded.tofile(str(target))
        for position, (k,target) in enumerate(zip(picks, output_paths), start=1):
            appended.append({
                "image":target.name,"video":video.name,"group_id":card["group_id"],
                "card_id":card["card_id"],"direction":direction,
                "frame_index":int(idx[k]),"frame_time_seconds":f"{idx[k]/fps:.3f}",
                "sharpness":f"{focus[k]:.2f}","motion_progress":f"{progress[k]:.4f}",
                "selection_method":("estimated_near_front_and_sharpness" if args.selection == "near-front"
                                    else "visual_change_and_sharpness"),
                "selected_position":position,
                "note":(f"ESTIMATED only: within +/-{args.max_angle:g} degrees "
                        f"if sweep +/-{args.sweep_half_angle:g} degrees and motion progress "
                        f"is linear; REVIEW actual viewpoint" if args.selection == "near-front"
                        else "REVIEW viewpoint, blur, card completeness, and labels"),
            })
        print(f"{video.name}: frames={len(idx)} selected={selected} progress="
              f"{[round(float(progress[i]),2) for i in picks]}")
    if appended:
        changed_videos = {r["video"] for r in appended}
        rows = [r for r in old_rows if r.get("video") not in changed_videos] + appended
        with report.open("w",encoding="utf-8-sig",newline="") as f:
            writer = csv.DictWriter(f,fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved {len(appended)} frames. Report: {report}")
    else:
        print("No new frames saved.")
    print("Selection is speed-adaptive, NOT calibrated to physical degrees. Check every image.")


if __name__ == "__main__":
    main()
