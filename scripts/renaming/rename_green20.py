"""Rename 20 original green karuta photographs safely.

Usage:
    uv run python scripts/rename_green20.py
    uv run python scripts/rename_green20.py --apply
    uv run python scripts/rename_green20.py --session s02
    uv run python scripts/rename_green20.py --session s02 --apply

Files must already be placed in data/raw/green20/top/h01_sXX in D01-D20 order.
Dry-run is the default. Confirm the displayed mapping before using --apply.
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_SCRIPTS_DIR = _Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS_DIR))


import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAPPING_CSV = ROOT / "data/metadata/green20_cards.csv"
EXTENSIONS = {".jpg", ".jpeg", ".png"}


def natural_key(path: Path) -> list[object]:
    return [
        int(token) if token.isdigit() else token.lower()
        for token in re.split(r"(\d+)", path.name)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview/rename 20 green karuta photos.")
    parser.add_argument("--folder", type=Path, default=None, help="Optional input folder; defaults to top/{height}_{session}")
    parser.add_argument("--height", default="h01", choices=["h01", "h02", "h03"])
    parser.add_argument("--session", default="s02", help="Session ID, e.g. s02 (default s02)")
    parser.add_argument("--apply", action="store_true", help="Perform rename after checking preview")
    args = parser.parse_args()

    if not re.fullmatch(r"s\d{2}", args.session):
        parser.error("--session must look like s01 or s02")
    folder = (args.folder if args.folder is not None else
              ROOT / "data/raw/green20/top" / f"{args.height}_{args.session}").resolve()
    if not folder.is_dir():
        parser.error(f"Folder does not exist: {folder}")

    with MAPPING_CSV.open(encoding="utf-8-sig", newline="") as f:
        records = sorted(csv.DictReader(f), key=lambda row: row["group_id"])
    if len(records) != 20 or len({r["card_id"] for r in records}) != 20:
        raise ValueError("Expected exactly 20 unique card IDs in mapping CSV")

    photos = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS),
        key=natural_key,
    )
    if len(photos) != 20:
        raise ValueError(f"Expected exactly 20 image files, found {len(photos)} in {folder}")

    changes = []
    for photo, record in zip(photos, records):
        card_id = record["card_id"]
        name = f"card_{card_id}_top_{args.height}_{args.session}{photo.suffix.lower()}"
        destination = folder / name
        changes.append((photo, destination, record["group_id"]))

    destinations = [dst for _, dst, _ in changes]
    if len(set(destinations)) != 20:
        raise ValueError("Duplicate destination filenames")
    source_paths = {src for src, _, _ in changes}
    if any(dst.exists() and dst != src for src, dst, _ in changes):
        raise FileExistsError("One or more destination filenames already exist")
    if any(dst in source_paths and dst != src for src, dst, _ in changes):
        raise ValueError("Filename collision with a different source; rename manually first")

    print(f"Folder: {folder}")
    print("IMPORTANT: Sorting by filename, not EXIF timestamp. Match D01-D20 manually!")
    for src, dst, group in changes:
        print(f"{group}: {src.name} -> {dst.name}")

    if not args.apply:
        print("\nPREVIEW ONLY. No files were changed. Add --apply after checking all 20.")
        return

    for src, dst, _ in changes:
        src.rename(dst)
    print("\nRenamed all 20 photographs successfully.")


if __name__ == "__main__":
    main()
