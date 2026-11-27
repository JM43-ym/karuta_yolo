"""Create synthetic 2-card and 3-card Train while preserving old Train8520/Val60.

Run without --build to check. Inspect generated previews before training.
Cards are segmented by Otsu threshold on the bright card center, with a
dilated convex-hull mask to preserve the green edge. Verify each preview.
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = ROOT / "data/datasets/green20_near_front_multi_val"
DEFAULT_OUT = ROOT / "data/datasets/green20_near_front_synthetic_multi_train"
EXT = {".png", ".jpg", ".jpeg"}


def read_image(path):
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unreadable image: {path}")
    return image


def save_image(path, image):
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise OSError(f"Encoding failed: {path}")
    encoded.tofile(str(path))


def read_label(path):
    rows = [r.split() for r in path.read_text(encoding="utf-8-sig").splitlines() if r.strip()]
    if len(rows) != 1 or len(rows[0]) != 5:
        raise ValueError(f"Expected one YOLO box: {path}")
    cls = int(rows[0][0])
    box = [float(v) for v in rows[0][1:]]
    if cls not in range(20) or not all(math.isfinite(v) and 0 <= v <= 1 for v in box) or min(box[2:]) <= 0:
        raise ValueError(f"Invalid YOLO label: {path}")
    return cls, box


def cutout(image, box, filename):
    h, w = image.shape[:2]
    cx, cy, bw, bh = box
    x0, x1 = max(0, int((cx - bw/2)*w)), min(w, math.ceil((cx + bw/2)*w))
    y0, y1 = max(0, int((cy - bh/2)*h)), min(h, math.ceil((cy + bh/2)*h))
    region = image[y0:y1, x0:x1]
    if min(region.shape[:2]) < 32:
        raise ValueError(f"Invalid crop: {filename}")
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError(f"No card foreground: {filename}")
    largest = max(contours, key=cv2.contourArea)
    fraction = cv2.contourArea(largest) / gray.size
    if not .2 <= fraction <= .96:
        raise ValueError(f"Suspect foreground {fraction:.2f}: {filename}")
    mask = np.zeros(gray.shape, np.uint8)
    cv2.fillConvexPoly(mask, cv2.convexHull(largest), 255)
    pad = max(3, round(min(gray.shape)*.025))
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*pad+1,2*pad+1)))
    ys, xs = np.where(mask > 0)
    l, r, t, b = xs.min(), xs.max()+1, ys.min(), ys.max()+1
    return region[t:b,l:r], mask[t:b,l:r]


def make_background(h, w, rng):
    level = rng.randrange(65, 100)
    slope_y = np.linspace(-4,4,h, dtype=np.float32)[:,None]
    slope_x = np.linspace(-3,3,w, dtype=np.float32)[None,:]
    noise = np.random.default_rng(rng.randrange(2**32)).normal(0,1.8,(h,w))
    gray = np.clip(level+slope_y+slope_x+noise,0,255).astype(np.uint8)
    return cv2.cvtColor(gray,cv2.COLOR_GRAY2BGR)


def compose(cutouts, shape, rng):
    h,w=shape[:2]
    height = rng.randrange(220, 285)  # Approximate h03 card height in 1440x1080
    cards=[]
    for crop, mask in cutouts:
        scale = height/crop.shape[0]*rng.uniform(.96,1.04)
        cw,ch = round(crop.shape[1]*scale),round(crop.shape[0]*scale)
        cards.append((cv2.resize(crop,(cw,ch)),cv2.resize(mask,(cw,ch),interpolation=cv2.INTER_NEAREST)))
    gap = rng.choice((0,0,3,6,12))
    total=sum(card.shape[1] for card,_ in cards)+gap*(len(cards)-1)
    if total>int(w*.8) or max(card.shape[0] for card,_ in cards)>int(h*.65):
        raise ValueError("Group too large for frame")
    x=rng.randint(max(8,round(w*.1)),max(9,round(w*.85-total)))
    y=rng.randint(max(8,round(h*.1)),max(9,round(h*.6)))
    positions=[]
    for card,mask in cards:
        ch,cw=card.shape[:2]
        yy=min(h-ch-2,max(2,y+rng.randint(-6,6)))
        positions.append((x,yy,card,mask))
        x += cw+gap
    return positions


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base",type=Path,default=DEFAULT_BASE)
    ap.add_argument("--output",type=Path,default=DEFAULT_OUT)
    ap.add_argument("--two",type=int,default=400)
    ap.add_argument("--three",type=int,default=400)
    ap.add_argument("--seed",type=int,default=20261127)
    ap.add_argument("--build",action="store_true")
    args=ap.parse_args()
    base,out=args.base.resolve(),args.output.resolve()
    if min(args.two,args.three)<0 or args.two+args.three<1:
        ap.error("At least one synthesis count must be positive")
    src_train=base/"images/train"
    src_labels=base/"labels/train"
    src_val=base/"images/val"
    src_val_labels=base/"labels/val"
    if not (base/"data.yaml").is_file() or not all(p.is_dir() for p in (src_train,src_labels,src_val,src_val_labels)):
        ap.error(f"Source dataset is missing: {base}")
    with (base/"data.yaml").open(encoding="utf-8-sig") as f:
        cfg=yaml.safe_load(f)
    if cfg["nc"]!=20:
        ap.error("Expected 20-class source")
    names=cfg["names"]
    if isinstance(names,dict):
        names=[names[i] for i in range(20)]
    if len(names)!=20:
        ap.error("Expected 20 class names")
    train=sorted(p for p in src_train.iterdir() if p.suffix.lower() in EXT)
    val=sorted(p for p in src_val.iterdir() if p.suffix.lower() in EXT)
    if len(train)!=8520 or len(val)!=60:
        ap.error(f"Expected Train8520/Val60; got Train{len(train)}/Val{len(val)}")
    for p in train:
        if not (src_labels/(p.stem+".txt")).is_file():
            ap.error(f"Missing Train label: {p}")
    for p in val:
        if not (src_val_labels/(p.stem+".txt")).is_file():
            ap.error(f"Missing Val label: {p}")
    # Select Train h03-like scale only, not any Val or Test image.
    by_class={i:[] for i in range(20)}
    for p in train:
        if "_scale2_" in p.stem:
            cls,_=read_label(src_labels/(p.stem+".txt"))
            by_class[cls].append(p)
    if any(not files for files in by_class.values()):
        ap.error("Missing Train scale2 variants for some classes")
    print(f"CHECK OK: existing Train={len(train)}, Val={len(val)}, all 20 classes available")
    print(f"Planned new Train={len(train)+args.two+args.three}: 2-card +{args.two}, 3-card +{args.three}")
    if not args.build:
        print("Dry run only. Use --build to create output.")
        return
    if out.exists() or out==base or out==ROOT or base in out.parents or (ROOT/"data/raw") in out.parents:
        ap.error(f"Output exists or invalid: {out}")
    images=out/"images/train"
    labels=out/"labels/train"
    previews=out/"previews"
    for path in (images,labels,previews):
        path.mkdir(parents=True,exist_ok=True)
    rng=random.Random(args.seed)
    card_cache={}
    stats=Counter()
    manifest=[]
    try:
        for n,count in ((2,args.two),(3,args.three)):
            for index in range(count):
                classes=rng.sample(range(20),n)
                chosen=[]
                names_used=[]
                shape=None
                for cls in classes:
                    for attempt in range(16):
                        src=rng.choice(by_class[cls])
                        try:
                            if src not in card_cache:
                                source_image=read_image(src)
                                _,bbox=read_label(src_labels/(src.stem+".txt"))
                                card_cache[src]=cutout(source_image,bbox,src.name)
                            chosen.append(card_cache[src])
                            names_used.append(src.name)
                            if shape is None:
                                shape=read_image(src).shape
                            break
                        except (ValueError,OSError):
                            if attempt==15:
                                raise
                canvas=make_background(shape[0],shape[1],rng)
                positions=compose(chosen,shape,rng)
                preview=canvas.copy()
                lines=[]
                for cls,(xx,yy,card,mask) in zip(classes,positions):
                    ch,cw=card.shape[:2]
                    canvas[yy:yy+ch,xx:xx+cw][mask>0]=card[mask>0]
                    ys,xs=np.where(mask>0)
                    x0,x1=xx+int(xs.min()),xx+int(xs.max())+1
                    y0,y1=yy+int(ys.min()),yy+int(ys.max())+1
                    H,W=canvas.shape[:2]
                    lines.append(f"{cls} {(x0+x1)/2/W:.6f} {(y0+y1)/2/H:.6f} {(x1-x0)/W:.6f} {(y1-y0)/H:.6f}")
                    cv2.rectangle(preview,(x0,y0),(x1,y1),(0,165,255),2)
                    cv2.putText(preview,str(names[cls]),(x0,max(15,y0-6)),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
                    stats[cls]+=1
                stem=f"synth_{n}cards_{index+1:04d}"
                save_image(images/(stem+".png"),canvas)
                (labels/(stem+".txt")).write_text("\n".join(lines)+"\n",encoding="utf-8")
                if index<12:
                    save_image(previews/(stem+"_preview.png"),preview)
                manifest.append([stem,n,";".join(names_used),";".join(str(c) for c in classes)])
        cfg_out={
            "path":out.as_posix(),
            "train":[src_train.as_posix(),images.as_posix()],
            "val":src_val.as_posix(),
            "nc":20,
            "names":{i:str(v) for i,v in enumerate(names)}
        }
        (out/"data.yaml").write_text(yaml.safe_dump(cfg_out,sort_keys=False,allow_unicode=True),encoding="utf-8")
        with (out/"source_manifest.csv").open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.writer(f)
            writer.writerow(["synthetic_stem","card_count","source_train_images","class_ids"])
            writer.writerows(manifest)
    except Exception:
        print(f"Failed: incomplete output retained for inspection at {out}")
        raise
    print(f"READY: Train={8520+args.two+args.three} Val=60; YAML={out/'data.yaml'}")
    print("Review synthetic previews and labels manually before training.")


if __name__=="__main__":
    main()
