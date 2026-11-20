"""BU160MCF / pytelicam live capture: one LR and one FB video per card.

Usage:
  uv run python scripts/capture_karuta_video.py --color blue20 --direction LR
  uv run python scripts/capture_karuta_video.py --color blue20 --direction FB --start 6

Keys: R start/stop this card, N next card, P previous card, Q / Esc quit.
Nothing overwrites an existing video. See docs/VIDEO_CAPTURE.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COLORS = ("green20", "blue20", "pink20", "yellow20", "orange20")
DIRECTIONS = ("LR", "FB")


class TeliCamera:
    """Simple TeliCamSDK / pytelicam streaming adapter (SDK wheel installed separately)."""

    def __init__(self, index: int):
        try:
            import pytelicam
        except ImportError as exc:
            raise RuntimeError(
                "pytelicam not installed. Install TeliCamSDK and the matching "
                "Python wheel from Toshiba Teli (see docs/VIDEO_CAPTURE.md)."
            ) from exc
        self.api = pytelicam
        self.system = pytelicam.get_camera_system()
        self.device = None
        try:
            n = self.system.get_num_of_cameras()
            if not (0 <= index < n):
                raise RuntimeError(f"Camera index {index} invalid; TeliCamSDK detects {n} cameras")
            # SDK defaults to the first discovered device when index=0.
            try:
                self.device = self.system.create_device_object(index)
            except TypeError:
                if index != 0:
                    raise RuntimeError("This pytelicam version does not support nonzero --camera-index")
                self.device = self.system.create_device_object()
            self.device.open()
            self.device.cam_stream.open()
            self.device.cam_stream.start()
        except Exception:
            self.close()
            raise

    def read(self) -> np.ndarray:
        img = self.device.cam_stream.get_next_image()
        if img is None:
            raise RuntimeError("Camera returned no image")
        try:
            frame = np.asarray(img.get_ndarray(self.api.OutputImageType.Bgr24)).copy()
            if frame.ndim != 3 or frame.shape[2] != 3:
                raise RuntimeError(f"Unexpected camera frame shape: {frame.shape}")
            return frame
        finally:
            img.release()

    def close(self):
        if self.device is not None:
            for f in (
                lambda: self.device.cam_stream.stop(),
                lambda: self.device.cam_stream.close(),
                lambda: self.device.close(),
            ):
                try:
                    f()
                except Exception:
                    pass
            self.device = None
        if self.system is not None:
            try:
                self.system.terminate()
            except Exception:
                pass
            self.system = None


def load_cards(color: str) -> list[dict[str, str]]:
    csv_path = ROOT / "data/metadata" / f"{color}_cards.csv"
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if len(rows) != 20:
        raise ValueError(f"Expected 20 mapping rows in {csv_path}")
    return rows


def draw_preview(frame, label: str, recording: bool, count: int, max_width: int):
    h, w = frame.shape[:2]
    scale = min(1.0, max_width / w)
    vis = cv2.resize(frame, (round(w * scale), round(h * scale))) if scale < 1 else frame.copy()
    cv2.rectangle(vis, (0, 0), (vis.shape[1], 70), (30, 30, 30), -1)
    cv2.putText(vis, label, (14, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.57, (245, 245, 245), 2)
    cv2.putText(vis, f"{'REC' if recording else 'READY'}  {count} frames  |  R: record/stop  N/P: card  Q: quit",
                (14, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                (0, 90, 255) if recording else (100, 240, 120), 1)
    return vis


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--color", choices=COLORS, required=True)
    parser.add_argument("--direction", choices=DIRECTIONS, required=True)
    parser.add_argument("--session", default="s01")
    parser.add_argument("--start", type=int, default=1, help="Group order, 1..20")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--fps", type=float, default=15.0, help="AVI playback FPS; actual acquisition is logged")
    parser.add_argument("--preview-width", type=int, default=960)
    args = parser.parse_args()
    if not (1 <= args.start <= 20 and args.fps > 0 and args.preview_width >= 200):
        parser.error("Invalid --start / --fps / --preview-width")
    if not args.session.startswith("s") or not args.session[1:].isdigit():
        parser.error("--session must be like s01")
    cards = load_cards(args.color)
    dest = ROOT / "data/raw" / args.color / "train/single/oblique/videos" / f"h01_{args.session}" / args.direction
    dest.mkdir(parents=True, exist_ok=True)
    capture_log = dest / "capture_index.csv"
    camera = TeliCamera(args.camera_index)
    index = args.start - 1
    writer = None
    video_path = None
    started = 0.0
    started_iso = ""
    count = 0
    try:
        cv2.namedWindow("Karuta Capture", cv2.WINDOW_NORMAL)
        while True:
            frame = camera.read()
            row = cards[index]
            group = row["group_id"]
            card_id = row["card_id"]
            label = f"{args.color} {group} / {card_id}  {args.direction}  h01_{args.session}"
            if writer is not None:
                writer.write(frame)
                count += 1
            cv2.imshow("Karuta Capture", draw_preview(frame, label, writer is not None, count, args.preview_width))
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("r"):
                if writer is None:
                    video_path = dest / f"karuta_{index + 1:02d}_{args.direction}.avi"
                    if video_path.exists():
                        print(f"Already exists, will NOT overwrite: {video_path}")
                        continue
                    h, w = frame.shape[:2]
                    new_writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"),
                                                 args.fps, (w, h))
                    if not new_writer.isOpened():
                        raise RuntimeError("Could not open MJPG AVI VideoWriter")
                    writer = new_writer
                    started = time.monotonic()
                    started_iso = datetime.now().astimezone().isoformat(timespec="seconds")
                    count = 0
                    print(f"REC START: {label}: {video_path}")
                else:
                    writer.release()
                    writer = None
                    finished_iso = datetime.now().astimezone().isoformat(timespec="seconds")
                    elapsed = time.monotonic() - started
                    record = dict(group_id=group, card_id=card_id, direction=args.direction,
                                  video=str(video_path.relative_to(ROOT)),
                                  started_at=started_iso, finished_at=finished_iso,
                                  elapsed_seconds=f"{elapsed:.2f}", frames=count,
                                  observed_fps=f"{count / max(elapsed, .01):.2f}",
                                  file_fps=args.fps, width=frame.shape[1], height=frame.shape[0])
                    write_header = not capture_log.exists()
                    with capture_log.open("a", encoding="utf-8-sig" if write_header else "utf-8",
                                          newline="") as output:
                        csv_writer = csv.DictWriter(output, fieldnames=list(record))
                        if write_header:
                            csv_writer.writeheader()
                        csv_writer.writerow(record)
                    print(f"REC SAVED: {video_path} ({count} frames; {elapsed:.1f}s)")
                    if count == 0:
                        print("WARNING: video has zero frames; do not use")
            if key in (ord("n"), ord("p")):
                if writer is not None:
                    print("Stop recording (R) before switching cards.")
                else:
                    index = max(0, min(19, index + (1 if key == ord("n") else -1)))
    finally:
        if writer is not None:
            writer.release()
            print(f"WARNING: interrupted while recording {video_path}; inspect it before using.")
        camera.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
