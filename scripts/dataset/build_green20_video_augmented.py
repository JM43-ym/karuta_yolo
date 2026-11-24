"""Check and build green20 dataset: 8520 augmented Train + 180 original Val.

Default checks only; --build requires explicit independent-validation confirmation.
Existing raw images, annotations, and datasets are never modified.
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
from pathlib import Path

import cv2
import numpy as np

from dataset.generate_rotations import ROOT, load_image, save_png, get_corners, rotation, xywh_from_corners, write_label
from annotation.annotate_green20_val_angles import ANGLES, SOURCE as FIXED_SOURCE, OUTPUT as FIXED_ANN

RAW=ROOT/"data/raw/green20"
ANN=ROOT/"data/annotations"
VIDEO=ANN/"video_frames/green20/h01_s01"
OUT=ROOT/"data/datasets/green20_video_augmented"
EXT={".png",".jpg",".jpeg"}


def read_csv(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def image_files(folder):
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXT)


def map_green():
    rows=sorted(read_csv(ROOT/"data/metadata/green20_cards.csv"),key=lambda r:r["group_id"])
    if len(rows)!=20 or len({r["card_id"] for r in rows})!=20:
        raise ValueError("Metadata must have 20 unique green cards")
    return {int(row["card_id"]):i for i,row in enumerate(rows)}, [f"{int(r['card_id']):03d}" for r in rows]


def parse_box(path,expected_class):
    if not path.is_file():
        raise FileNotFoundError(f"Missing label: {path}")
    lines=path.read_text(encoding="utf-8").strip().splitlines()
    if len(lines)!=1:
        raise ValueError(f"Expected one YOLO box: {path}")
    vals=lines[0].split()
    if len(vals)!=5 or int(vals[0])!=expected_class:
        raise ValueError(f"Incorrect class/bbox: {path}")
    box=[float(x) for x in vals[1:]]
    if not all(math.isfinite(v) and 0<=v<=1 for v in box) or min(box[2:])<=0:
        raise ValueError(f"Invalid normalized coordinates: {path}")
    return box


def top_sources(height,session,mapping):
    split="train" if session=="s01" else "val"
    folder=RAW/split/"single/top"/f"{height}_{session}"
    ann=ANN/f"green20_{height}_{session}"
    rows=read_csv(ann/"report.csv")
    by_name={r["filename"]:r for r in rows}
    files=image_files(folder)
    if len(files)!=20 or set(by_name)!={p.name for p in files}:
        raise ValueError(f"Top session expected 20 matching report entries: {folder}")
    out=[]
    for p in files:
        row=by_name[p.name]
        cid=int(row["card_id"])
        if cid not in mapping or int(row["class_id"])!=mapping[cid]:
            raise ValueError(f"Top class mismatch: {p}")
        parse_box(ann/"labels"/(p.stem+".txt"),mapping[cid])
        img=load_image(p)
        corners=get_corners(row,p,img.shape)
        out.append((p,mapping[cid],corners))
    return out


def scale_by_area(top):
    # Use card area relative to frame area for consistency across resolutions.
    measurements=[]
    for p,_,pts in top:
        img=load_image(p)
        frac=abs(cv2.contourArea(pts.astype(np.float32)))/(img.shape[0]*img.shape[1])
        if not .0001<frac<.95:
            raise ValueError(f"Invalid top card size: {p}")
        measurements.append(math.sqrt(frac))
    return float(np.median(measurements))


def video_sources(mapping):
    all_items=[]
    for direction in ("LR","FB"):
        folder=RAW/"train/single/oblique/extracted/h01_s01"/direction
        labels=VIDEO/f"{direction}_annotated"/"labels"
        images=image_files(folder)
        if len(images)!=100:
            raise ValueError(f"Expected 100 {direction} video images, got {len(images)}: {folder}")
        per_card={cid:0 for cid in mapping}
        for p in images:
            import re
            m=re.fullmatch(r"card_(\d{3})_(LR|FB)_h01_s01_f\d{6}\.png",p.name,re.I)
            if not m or m.group(2).upper()!=direction:
                raise ValueError(f"Unexpected video filename: {p}")
            cid=int(m.group(1))
            if cid not in mapping:
                raise ValueError(f"Unknown green card: {p}")
            per_card[cid]+=1
            # Video labels use GLOBAL class id (card_id-1); convert to 20 local.
            box=parse_box(labels/(p.stem+".txt"),cid-1)
            all_items.append((p,mapping[cid],box,direction))
        if any(v!=5 for v in per_card.values()):
            raise ValueError(f"Each green card needs five {direction} images; counts: {per_card}")
    return all_items


def fixed_val(mapping):
    out=[]
    for angle in ANGLES:
        folder=FIXED_SOURCE/angle
        labels=FIXED_ANN/angle/"labels"
        photos=image_files(folder)
        if len(photos)!=20:
            raise ValueError(f"Expected 20 images in {folder}; got {len(photos)}")
        seen=set()
        for p in photos:
            import re
            m=re.fullmatch(r"card_(\d{3})_"+angle+r"_s02\.(png|jpg|jpeg)",p.name,re.I)
            if not m:
                raise ValueError(f"Unexpected fixed-angle name: {p}")
            cid=int(m.group(1))
            if cid not in mapping or cid in seen:
                raise ValueError(f"Duplicate/unknown card: {p}")
            seen.add(cid)
            box=parse_box(labels/(p.stem+".txt"),mapping[cid])
            out.append((p,mapping[cid],box))
        if seen!=set(mapping):
            raise ValueError(f"Missing cards at {angle}")
    return out


def get_corners_from_normalized(box,shape):
    h,w=shape[:2]
    cx,cy,bw,bh=box
    return np.float32([[(cx-bw/2)*w,(cy-bh/2)*h],
                       [(cx+bw/2)*w,(cy-bh/2)*h],
                       [(cx+bw/2)*w,(cy+bh/2)*h],
                       [(cx-bw/2)*w,(cy+bh/2)*h]])


def augment_scaled(img,corners,scale,angle):
    # Keep the image canvas FIXED. Scaling the whole canvas along with the
    # card would cancel the intended apparent-size augmentation.
    h,w=img.shape[:2]
    mat=cv2.getRotationMatrix2D((w/2,h/2),angle,scale)
    new_pts=cv2.transform(corners.reshape(1,4,2),mat)[0]
    # Never write labels for truncated cards.
    bbox=xywh_from_corners(new_pts,w,h)
    out=cv2.warpAffine(img,mat,(w,h),
                       flags=cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT,
                       borderValue=(0,0,0))
    return out,bbox


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--build",action="store_true",help="Create new dataset after checks")
    ap.add_argument("--confirm-independent-val",action="store_true",
                    help="I verified fixed-angle and s02 images are independent of training captures")
    ap.add_argument("--output",type=Path,default=OUT)
    args=ap.parse_args()
    mapping,names=map_green()
    tops={h:top_sources(h,"s01",mapping) for h in ("h01","h02","h03")}
    sizes={h:scale_by_area(items) for h,items in tops.items()}
    scales=[1.,sizes["h02"]/sizes["h01"],sizes["h03"]/sizes["h01"]]
    if not all(math.isfinite(s) and .25<s<4 for s in scales):
        raise ValueError(f"Implausible measured scales: {scales}")
    print("Measured relative card sizes, normalized by image area:",sizes)
    print(f"Three train scales: h01=1, h02={scales[1]:.5f}, h03={scales[2]:.5f}")
    video=video_sources(mapping)
    fixed=fixed_val(mapping)
    front=RAW/"val/single/top/h01_s02"
    val_height="h01" if front.is_dir() else "h03"
    val_top=top_sources(val_height,"s02",mapping)
    if len(video)!=200 or len(fixed)!=160 or len(val_top)!=20:
        raise ValueError("Wrong number of data sources")
    print("Validated: Train video 200 + Train top 20; Val fixed 160 + s02 top 20")
    print("Planned: Train 8520 images; Val 180 original images. No flips, no Test.")
    if not args.build:
        print("CHECK ONLY. No files changed. Review independence then use --build --confirm-independent-val.")
        return
    if not args.confirm_independent_val:
        ap.error("--build requires --confirm-independent-val (verify photo-session independence)")
    dest=(args.output if args.output.is_absolute() else ROOT/args.output).resolve()
    if dest.exists():
        ap.error(f"Output already exists; no overwrite allowed: {dest}")
    if dest==ROOT or RAW in dest.parents or ANN in dest.parents:
        ap.error("Unsafe output path")
    train_dir=dest/"images/train"
    val_dir=dest/"images/val"
    for d in (train_dir,val_dir,dest/"labels/train",dest/"labels/val"):
        d.mkdir(parents=True,exist_ok=True)
    total=0
    try:
        for p,cls,box,direction in video:
            img=load_image(p)
            pts=get_corners_from_normalized(box,img.shape)
            for scale_idx,scale in enumerate(scales):
                for angle in range(-15,16,5):
                    warped,xywh=augment_scaled(img,pts,scale,angle)
                    stem=f"{p.stem}_scale{scale_idx}_rot{angle:+03d}".replace("+","p").replace("-","m")
                    save_png(train_dir/(stem+".png"),warped)
                    write_label(dest/"labels/train"/(stem+".txt"),cls,xywh)
                    total+=1
        for p,cls,pts in tops["h01"]:
            img=load_image(p)
            for scale_idx,scale in enumerate(scales):
                for angle in range(0,360,5):
                    warped,xywh=augment_scaled(img,pts,scale,angle)
                    stem=f"{p.stem}_scale{scale_idx}_rot{angle:03d}"
                    save_png(train_dir/(stem+".png"),warped)
                    write_label(dest/"labels/train"/(stem+".txt"),cls,xywh)
                    total+=1
        for p,cls,box in fixed:
            name=f"fixed_{p.stem}"
            save_png(val_dir/(name+".png"),load_image(p))
            write_label(dest/"labels/val"/(name+".txt"),cls,box)
        for p,cls,pts in val_top:
            img=load_image(p)
            h,w=img.shape[:2]
            xywh=xywh_from_corners(pts,w,h)
            name=f"top_{p.stem}"
            save_png(val_dir/(name+".png"),img)
            write_label(dest/"labels/val"/(name+".txt"),cls,xywh)
        if total!=8520 or len(list(val_dir.glob("*.png")))!=180:
            raise ValueError(f"Dataset unexpected counts: train={total} val={len(list(val_dir.glob('*.png')))}")
        lines=[f"path: '{dest.as_posix()}'","train: images/train","val: images/val",
               "nc: 20","names:"]
        lines += [f"  {i}: '{cid}'" for i,cid in enumerate(names)]
        (dest/"data.yaml").write_text("\n".join(lines)+"\n",encoding="utf-8")
        with (dest/"build_summary.csv").open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.writer(f)
            writer.writerow(["source_height","normalized_card_size","applied_scale_from_h01"])
            for h,s in zip(("h01","h02","h03"),scales):
                writer.writerow([h,f"{sizes[h]:.7f}",f"{s:.7f}"])
    except Exception:
        print("Build interrupted. Incomplete output retained for inspection; no source files changed:",dest)
        raise
    print(f"READY: {total} Train + 180 Val. YAML: {dest/'data.yaml'}")
    print("Disable flipud/fliplr and unwanted automatic augmentation when training.")


if __name__=="__main__":
    main()
