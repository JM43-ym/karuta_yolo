"""Check the reorganized green20 raw photo paths without moving any files.

Run: uv run python scripts/check_green20_paths.py
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_SCRIPTS_DIR = _Path(__file__).resolve().parents[2]
if str(_SCRIPTS_DIR) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS_DIR))


from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"data/raw/green20"
EXT={".png",".jpg",".jpeg"}


def count_images(directory:Path)->int:
    return sum(p.is_file() and p.suffix.lower() in EXT for p in directory.iterdir())


def main():
    required={
        "train singles h01":BASE/"train/single/top/h01_s01",
        "train singles h02":BASE/"train/single/top/h02_s01",
        "train singles h03":BASE/"train/single/top/h03_s01",
        "val singles h03":BASE/"val/single/top/h03_s02",
        "val two cards":BASE/"val/multi/two_cards",
        "val three cards":BASE/"val/multi/three_cards",
    }
    optional={
        "legacy val singles h01":BASE/"val/single/top/h01_s02",
        "dev competition":BASE/"dev/competition",
        "train oblique":BASE/"train/single/oblique",
        "train scattered":BASE/"train/multi/scattered",
        "val scattered":BASE/"val/multi/scattered",
        "test scattered":BASE/"test/multi/scattered",
    }
    missing=0
    print("=== Required original photo directories ===")
    for label,path in required.items():
        if not path.is_dir():
            print(f"MISSING: {label}: {path}")
            missing+=1
        else:
            total=count_images(path)
            print(f"{label}: {total} images ({path.relative_to(ROOT)})")
            if total!=20:
                print("  WARNING: expected 20 images for this existing capture set")
    print("\n=== Optional/new photo directories ===")
    for label,path in optional.items():
        if path.is_dir():
            print(f"{label}: {count_images(path)} images ({path.relative_to(ROOT)})")
        else:
            print(f"{label}: not yet present")
    print("\nExisting data/datasets and runs are NOT changed.")
    if missing:
        raise SystemExit(f"{missing} required folders missing; verify files were moved as planned.")
    print("Required folder paths found; check image counts and filenames before rebuilding.")


if __name__=="__main__":
    main()
