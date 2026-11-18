"""Create upright-only YOLO dataset with independent h03 single/multi validation.

Training: 20 classes x 3 heights x 7 angles (-15..15 step 5) = 420 images.
Validation: reuse independently captured 60 images/120 cards from green20_v3.
No reflections. Keeps all prior datasets intact.

Run: uv run python scripts/build_green20_v4.py
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

from generate_rotations import (ROOT, RAW, ANNOTATIONS, session_sources,
                                load_image, get_corners, xywh_from_corners,
                                rotation, save_png, write_label)

DEFAULT = ROOT / "data/datasets/green20_v4"
OLD_VAL = ROOT / "data/datasets/green20_v3"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--max-angle", type=int, default=15,
                        help="Maximum absolute rotation (degrees); default 15")
    parser.add_argument("--step", type=int, default=5)
    args = parser.parse_args()
    if not (0 <= args.max_angle <= 45 and args.step > 0
            and args.max_angle % args.step == 0):
        parser.error("Use 0 <= max-angle <=45, positive step dividing max-angle")
    angles = list(range(-args.max_angle, args.max_angle + 1, args.step))
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error(f"Output already exists and is not empty: {output}. Existing datasets are never deleted.")
    if (output == ROOT or output == RAW or output == ANNOTATIONS or
        output == ROOT / "data" or output == OLD_VAL.resolve()):
        parser.error("Unsafe output directory")
    old_images = OLD_VAL / "images/val"
    old_labels = OLD_VAL / "labels/val"
    if not old_images.is_dir() or not old_labels.is_dir():
        parser.error("Missing green20_v3 validation set")
    val_images = sorted(old_images.glob("*.png"))
    if len(val_images) != 60 or len(list(old_labels.glob("*.txt"))) != 60:
        parser.error("Expected 60 images and 60 labels in v3 validation set")
    if sum(len((old_labels/(p.stem+".txt")).read_text(encoding="utf-8").splitlines())
           for p in val_images) != 120:
        parser.error("Expected 120 labeled card instances in v3 validation set")

    with (ROOT/"data/metadata/green20_cards.csv").open(encoding="utf-8-sig", newline="") as f:
        cards=list(csv.DictReader(f))
    card_to_class={int(r["card_id"]):i for i,r in enumerate(cards)}
    if len(cards) != 20 or len(card_to_class) != 20:
        parser.error("Class mapping must contain 20 unique cards")
    sources=[]
    for height in ("h01","h02","h03"):
        _, _, rows, images = session_sources(height,"s01")
        for photo in images:
            row=rows[photo.name]
            cid=int(row["card_id"])
            if cid not in card_to_class or int(row["class_id"])!=card_to_class[cid]:
                parser.error(f"Class mismatch: {photo}")
            original_label=ANNOTATIONS/f"green20_{height}_s01/labels"/(photo.stem+".txt")
            if not original_label.is_file():
                parser.error(f"Missing source label: {original_label}")
            image=load_image(photo)
            corners=get_corners(row,photo,image.shape)
            sources.append((photo,image,corners,card_to_class[cid]))
    if len(sources)!=60:
        parser.error("Expected 60 independent training source photos")

    for split in ("train","val"):
        (output/"images"/split).mkdir(parents=True,exist_ok=True)
        (output/"labels"/split).mkdir(parents=True,exist_ok=True)
    counter=0
    for i,(photo,image,corners,cid) in enumerate(sources,1):
        for angle in angles:
            if angle==0:
                transformed=image
                pts=corners
            else:
                transformed,pts=rotation(image,corners,angle)
            h,w=transformed.shape[:2]
            bbox=xywh_from_corners(pts,w,h)
            # Use direction marker so filenames are valid on Windows.
            tag=f"p{angle:02d}" if angle>=0 else f"m{-angle:02d}"
            stem=f"{photo.stem}_rot{tag}"
            save_png(output/"images/train"/(stem+".png"),transformed)
            write_label(output/"labels/train"/(stem+".txt"),cid,bbox)
            counter+=1
        print(f"{i:02d}/60: {photo.name} => {len(angles)} upright images")
    for photo in val_images:
        shutil.copy2(photo,output/"images/val"/photo.name)
        label=old_labels/(photo.stem+".txt")
        shutil.copy2(label,output/"labels/val"/label.name)

    names=[f"{int(r['card_id']):03d}（{r['decision_prefix']}）" for r in cards]
    lines=[f"path: '{output.as_posix()}'","train: images/train",
           "val: images/val","nc: 20","names:"]
    lines.extend(f"  {i}: '{name}'" for i,name in enumerate(names))
    (output/"data.yaml").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(f"Finished: {counter} upright train images ({len(angles)} angles), 60 val images / 120 cards.")
    print("No horizontal/vertical reflections generated. Training-time flips must ALSO be disabled.")
    print(f"Dataset: {output}")


if __name__=="__main__":
    main()
