"""Safely rename 20 independent green20 validation images for a fixed angle.

Examples (replace folder with ACTUAL folder):
 uv run --no-sync python scripts/rename_green20_val_angles.py --angle F30 --folder "data/raw/green20/val/single/oblique/F30"
 uv run --no-sync python scripts/rename_green20_val_angles.py --angle F30 --folder "data/raw/green20/val/single/oblique/F30" --apply --confirm-order

IMPORTANT: Natural filename order must ALREADY match D01-D20. Inspect the
printed mapping (and the photographs!) before using --apply.
No guessed mapping from image contents, timestamps or EXIF.
"""
from __future__ import annotations

import argparse
import csv
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANGLES = ("L30","L45","R30","R45","F30","F45","B30","B45")
EXTS = {".png",".jpg",".jpeg",".bmp",".tif",".tiff"}


def natural_key(p: Path):
    return [int(s) if s.isdigit() else s.casefold()
            for s in re.split(r"(\d+)",p.name)]


def main():
    parser=argparse.ArgumentParser(description=__doc__,
       formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--angle",required=True,choices=ANGLES)
    parser.add_argument("--folder",type=Path,required=True,
                        help="Folder with 20 images, in D01-D20 filename order")
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--confirm-order",action="store_true",
                        help="I visually confirmed the 20 images correspond to D01-D20")
    args=parser.parse_args()

    folder=(args.folder if args.folder.is_absolute()
            else ROOT/args.folder).resolve()
    if not folder.is_dir():
        parser.error(f"Folder does not exist: {folder}")
    with (ROOT/"data/metadata/green20_cards.csv").open(
            encoding="utf-8-sig",newline="") as f:
        cards=sorted(csv.DictReader(f),key=lambda row:row["group_id"])
    if len(cards)!=20 or len({c["card_id"] for c in cards})!=20:
        parser.error("Invalid green20 metadata; expected 20 unique cards")

    images=sorted((x for x in folder.iterdir()
                   if x.is_file() and x.suffix.lower() in EXTS),key=natural_key)
    if len(images)!=20:
        parser.error(f"Expected exactly 20 image files; found {len(images)}")
    changes=[]
    for image,card in zip(images,cards):
        dest=folder/f"card_{int(card['card_id']):03d}_{args.angle}_s02{image.suffix.lower()}"
        changes.append((image,dest,card))
    targets=[dst for _,dst,_ in changes]
    if len(targets)!=len(set(targets)):
        parser.error("Duplicate target file names")
    source_set={src for src,_,_ in changes}
    if any(dst.exists() and dst!=src for src,dst,_ in changes):
        parser.error("A target file already exists: refusing to overwrite")
    if any(dst in source_set and src!=dst for src,dst,_ in changes):
        parser.error("Mixed/renamed names: please inspect manually first")

    print(f"Angle: {args.angle} | Folder: {folder}")
    for src,dst,card in changes:
        print(f"{card['group_id']} / {int(card['card_id']):03d}: {src.name} -> {dst.name}")
    print("WARNING: filename order is NOT proof of card identity. Check each image against D01-D20.")
    if not args.apply:
        print("DRY RUN ONLY. No files changed. For confirmed order use --apply --confirm-order.")
        return
    if not args.confirm_order:
        parser.error("--apply also requires --confirm-order after visual checking")

    # Stage to unique temporary names so originals are never overwritten by
    # any future destination; revert on failures where possible.
    staged=[]
    finished=[]
    try:
        for src,dst,_ in changes:
            if src==dst:
                continue
            tmp=folder/(f".rename_stage_{uuid.uuid4().hex}{src.suffix}")
            src.rename(tmp)
            staged.append((src,tmp,dst))
        for src,tmp,dst in staged:
            tmp.rename(dst)
            finished.append((src,tmp,dst))
    except OSError:
        for src,tmp,dst in reversed(finished):
            if dst.exists() and not src.exists():
                dst.rename(src)
        for src,tmp,dst in reversed(staged):
            if tmp.exists() and not src.exists():
                tmp.rename(src)
        raise
    print(f"Renamed {len(staged)} images for {args.angle}.")
    print("Next: verify image identity and create/review labels before dataset building.")


if __name__=="__main__":
    main()
