"""Run an existing karuta_yolo script via a categorized command entry point.

The original scripts stay in scripts/ for compatibility with imports and
existing lab procedures. This is a transitional, non-destructive organizer.
"""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = {
    "annotation": {
        "top": "auto_annotate.py",
        "video": "annotate_karuta_frames.py",
        "fixed": "annotate_green20_val_angles.py",
        "manual": "manual_fix_karuta_frames.py",
        "review": "review_karuta_annotations.py",
    },
    "renaming": {
        "top": "rename_green20.py",
        "fixed": "rename_green20_val_angles.py",
    },
    "capture": {
        "frames": "extract_karuta_frames.py",
    },
    "dataset": {
        "build": "build_green20_video_augmented.py",
        "inspect": "dataset_inventory.py",
    },
    "training": {
        "train": "train_green20.py",
    },
    "inference": {
        "predict": "predict_green20.py",
    },
}
def main(category: str | None = None) -> None:
    parser = argparse.ArgumentParser(description="Category-organized karuta_yolo scripts")
    if category is None:
        parser.add_argument("category", nargs="?", choices=sorted(TOOLS))
        parser.add_argument("action", nargs="?")
        args, rest = parser.parse_known_args()
        category, action = args.category, args.action
    else:
        parser.add_argument("action", nargs="?")
        args, rest = parser.parse_known_args()
        action = args.action
    if not category or action not in TOOLS[category]:
        available = ", ".join(TOOLS.get(category, {})) if category else "annotation, renaming, capture, dataset, training, inference"
        parser.error(f"Choose a valid category/action. Available: {available}")
    src = ROOT / TOOLS[category][action]
    if not src.is_file():
        parser.error(f"Required script missing: {src}")
    sys.path.insert(0, str(ROOT))
    sys.argv = [str(src), *rest]
    runpy.run_path(str(src), run_name="__main__")
if __name__ == "__main__":
    main()
