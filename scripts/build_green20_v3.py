"""Build validation-focused v3 dataset without duplicating the 4320 v2 train PNGs.

v3/train points to green20_v2/images/train (same labels and images).
v3/val holds h03_s02 single cards + h03 2- and 3-card layouts.

Prerequisites: rename h03_s02, annotate it, annotate_multi_val.py and REVIEW previews.
Run: uv run python scripts/build_green20_v3.py
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

from generate_rotations import ROOT, load_image, read_report, get_corners, xywh_from_corners, save_png, write_label

RAW = ROOT / "data/raw/green20"
ANN = ROOT / "data/annotations"
V2 = ROOT / "data/datasets/green20_v2"
V3 = ROOT / "data/datasets/green20_v3"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=V3)
    args=parser.parse_args()
    dest=args.output.resolve()
    if dest.exists() and any(dest.iterdir()):
        parser.error(f"Output already exists and is not empty: {dest}. Remove it manually ONLY after checking its contents.")
    train_images=V2/"images/train"
    train_labels=V2/"labels/train"
    if not train_images.is_dir() or not train_labels.is_dir():
        parser.error("Missing green20_v2 train images/labels. Generate v2 first.")
    singles=RAW/"val/single/top/h03_s02"
    singles_report=read_report(ANN/"green20_h03_s02/report.csv")
    singles_files=sorted(singles.glob("*.png"))
    if len(singles_files)!=20 or {p.name for p in singles_files}!=set(singles_report):
        parser.error("Expected 20 matching h03_s02 photos and report entries")
    multi_ann=ANN/"green20_h03_multi_val"
    with (ROOT/"data/metadata/green20_val_layouts.csv").open(encoding="utf-8-sig",newline="") as f:
        layouts=list(csv.DictReader(f))
    if len(layouts)!=40 or len({r["filename"] for r in layouts})!=40:
        parser.error("Expected 40 distinct multi-card layouts")
    with (multi_ann/"report.csv").open(encoding="utf-8-sig",newline="") as f:
        report={r["filename"]:r for r in csv.DictReader(f)}
    if {r["filename"] for r in layouts}!=set(report):
        parser.error("Multi-card annotation report mismatches layout metadata")
    for r in layouts:
        name=r["filename"]
        prefix=name.split("_")[0]
        img=RAW/"val/multi"/(prefix+"_cards")/name
        label=multi_ann/"labels"/(Path(name).stem+".txt")
        if report[name]["status"]!="REVIEW" or not img.is_file() or not label.is_file():
            parser.error(f"Missing or failed multi-card annotation: {name}")
        lines=label.read_text(encoding="utf-8").strip().splitlines()
        expected=2 if prefix=="two" else 3
        if len(lines)!=expected:
            parser.error(f"Incorrect number of YOLO labels: {label}")
    with (ROOT/"data/metadata/green20_cards.csv").open(encoding="utf-8-sig",newline="") as f:
        cards=list(csv.DictReader(f))
    mapping={int(r["card_id"]):i for i,r in enumerate(cards)}
    for img in singles_files:
        row=singles_report[img.name]
        if int(row["class_id"])!=mapping[int(row["card_id"])]:
            parser.error(f"Class ID mismatch: {img}")
        label=ANN/"green20_h03_s02/labels"/(img.stem+".txt")
        if not label.is_file():
            parser.error(f"Missing label: {img}")
    (dest/"images/val").mkdir(parents=True)
    (dest/"labels/val").mkdir(parents=True)
    for img in singles_files:
        row=singles_report[img.name]
        image=load_image(img)
        corners=get_corners(row,img,image.shape)
        bbox=xywh_from_corners(corners,image.shape[1],image.shape[0])
        save_png(dest/"images/val"/img.name,image)
        write_label(dest/"labels/val"/(img.stem+".txt"),int(row["class_id"]),bbox)
    for r in layouts:
        img_name=r["filename"]
        prefix=img_name.split("_")[0]
        original=RAW/"val/multi"/(prefix+"_cards")/img_name
        label=multi_ann/"labels"/(Path(img_name).stem+".txt")
        shutil.copy2(original,dest/"images/val"/img_name)
        shutil.copy2(label,dest/"labels/val"/label.name)
    names=[f"{int(r['card_id']):03d}" for r in cards]
    # Keep names as numeric card IDs in labels; decision prefixes are shown by predict_green20.py.
    yaml_lines=[f"path: '{dest.as_posix()}'",
                f"train: '{train_images.resolve().as_posix()}'",
                "val: images/val","nc: 20","names:"]
    yaml_lines.extend(f"  {i}: '{n}'" for i,n in enumerate(names))
    (dest/"data.yaml").write_text("\n".join(yaml_lines)+"\n",encoding="utf-8")
    print(f"Ready: train = existing v2 (4320 images); val = 60 independent images (120 cards)")
    print(f"YAML: {dest/'data.yaml'}")
    print("All automatically generated multi-card labels require visual review before training.")


if __name__=="__main__":
    main()
