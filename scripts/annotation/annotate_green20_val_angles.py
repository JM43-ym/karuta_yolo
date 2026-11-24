"""Prepare provisional annotations for 8 fixed-angle green20 validation sets.

Run:
  uv run --no-sync python scripts/annotate_green20_val_angles.py
  uv run --no-sync python scripts/annotate_green20_val_angles.py --review
  uv run --no-sync python scripts/annotate_green20_val_angles.py --fix-missing

Never modifies source photographs or previously saved labels.
Assumes fixed-angle images have ALREADY been renamed to
card_008_F30_s02.png etc. Here "s02" is a filename tag only; it does not
prove an independent photo session.
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_SCRIPTS_DIR = _Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS_DIR))


import argparse
import csv
import html
import re
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from annotation.auto_annotate import read_image, save_image, make_annotation
from annotation.annotate_karuta_frames import (detect_green_quad, detect_fragmented_green,
                                     order_points)

ROOT = Path(__file__).resolve().parents[2]
ANGLES = ("L30","L45","R30","R45","F30","F45","B30","B45")
IMAGE = re.compile(r"^card_(\d{3})_(L30|L45|R30|R45|F30|F45|B30|B45)_s02\.(png|jpg|jpeg)$",re.I)
SOURCE = ROOT/"data/raw/green20/train/single/oblique/h01_s01"
OUTPUT = ROOT/"data/annotations/green20_fixed_angle_val"
FIELDS = ("image","card_id","group_id","class_id","status","method",
          "score","corner_points_px")
EXTS = (".png",".jpg",".jpeg")


def mappings():
    with (ROOT/"data/metadata/green20_cards.csv").open(encoding="utf-8-sig",newline="") as f:
        rows=sorted(csv.DictReader(f),key=lambda r:r["group_id"])
    if len(rows)!=20 or len({r["card_id"] for r in rows})!=20:
        raise ValueError("Expected 20 green cards")
    return {int(r["card_id"]):(r["group_id"],i) for i,r in enumerate(rows)}


def paths_for(angle):
    src=SOURCE/angle
    dest=OUTPUT/angle
    labels=dest/"labels"
    previews=dest/"previews"
    return src,dest,labels,previews


def collect(angle,lookup):
    src,*_=paths_for(angle)
    if not src.is_dir():
        raise FileNotFoundError(f"Missing source folder: {src}")
    images=sorted(p for p in src.iterdir() if p.suffix.lower() in EXTS)
    if len(images)!=20:
        raise ValueError(f"{angle}: Expected 20 images but found {len(images)}")
    used=set()
    for path in images:
        m=IMAGE.fullmatch(path.name)
        if m is None or m.group(2).upper()!=angle:
            raise ValueError(f"Unexpected filename (check rename): {path}")
        cid=int(m.group(1))
        if cid not in lookup or cid in used:
            raise ValueError(f"Unknown or duplicate card ID: {path}")
        used.add(cid)
    if used!=set(lookup):
        raise ValueError(f"Missing green20 cards in {angle}: {set(lookup)-used}")
    return images


def read_report(dest):
    file=dest/"annotation_report.csv"
    if not file.is_file():
        return {}
    with file.open(encoding="utf-8-sig",newline="") as f:
        return {r["image"]:r for r in csv.DictReader(f)}


def write_report(dest,rows):
    dest.mkdir(parents=True,exist_ok=True)
    with (dest/"annotation_report.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def preview(img,corners,text):
    vis=img.copy()
    h,w=img.shape[:2]
    cv2.polylines(vis,[corners.astype(np.int32)],True,(0,165,255),3)
    xywh=make_annotation(img,corners)
    if xywh is None:
        raise ValueError("Invalid bbox")
    cx,cy,bw,bh=xywh
    cv2.rectangle(vis,(int((cx-bw/2)*w),int((cy-bh/2)*h)),
                  (int((cx+bw/2)*w),int((cy+bh/2)*h)),(255,210,0),2)
    cv2.putText(vis,text,(10,35),cv2.FONT_HERSHEY_SIMPLEX,.60,(0,0,255),2)
    scale=min(1.,1100./max(h,w))
    if scale<1:
        vis=cv2.resize(vis,(round(w*scale),round(h*scale)))
    return vis,xywh


def run_auto(angle,lookup):
    images=collect(angle,lookup)
    _,dest,labels,previews=paths_for(angle)
    labels.mkdir(parents=True,exist_ok=True)
    previews.mkdir(parents=True,exist_ok=True)
    previous=read_report(dest)
    rows=[]
    for path in images:
        cid=int(IMAGE.fullmatch(path.name).group(1))
        group,cls=lookup[cid]
        row={k:"" for k in FIELDS}
        row.update(image=path.name,card_id=f"{cid:03d}",group_id=group,class_id=str(cls))
        label=labels/(path.stem+".txt")
        if label.exists():
            old=previous.get(path.name,{})
            row.update({k:old.get(k,row.get(k,"")) for k in FIELDS})
            row["status"]=old.get("status") if old.get("status") in ("REVIEW","MANUAL_REVIEW") else "EXISTING_LABEL_REVIEW"
            rows.append(row)
            continue
        try:
            img=read_image(path)
            # Fixed-angle cards are not always upright. Keep v3 detector
            # unchanged; it already considers convex quads and ink texture.
            proposals=detect_green_quad(img,"FB")
            if not proposals:
                proposals=detect_fragmented_green(img,"FB")
            if not proposals:
                row["status"]="FAIL: no reliable green outline"
                vis=img.copy()
                cv2.putText(vis,"MANUAL CORNERS NEEDED",(10,35),
                            cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,255),2)
                scale=min(1.,1100/max(img.shape[:2]))
                if scale<1:
                    vis=cv2.resize(vis,None,fx=scale,fy=scale)
                save_image(previews/(path.stem+".jpg"),vis)
            else:
                score,corners,method,_,_=proposals[0]
                vis,box=preview(img,corners,f"{group} / {angle} / REVIEW")
                save_image(previews/(path.stem+".jpg"),vis)
                label.write_text(str(cls)+" "+" ".join(f"{v:.6f}" for v in box)+"\n",
                                 encoding="utf-8")
                row.update(status="REVIEW",method=method,score=f"{score:.4f}",
                           corner_points_px=";".join(f"{x:.1f},{y:.1f}" for x,y in corners))
        except (ValueError,OSError,cv2.error) as e:
            row["status"]="FAIL: "+str(e)
        rows.append(row)
        print(f"{angle} {path.name}: {row['status']}")
    write_report(dest,rows)
    return Counter(row["status"] for row in rows)


def run_manual(angle,lookup):
    images=collect(angle,lookup)
    _,dest,labels,previews=paths_for(angle)
    if not dest.exists():
        raise FileNotFoundError(f"Run automatic annotation first for {angle}")
    labels.mkdir(exist_ok=True,parents=True)
    previews.mkdir(exist_ok=True,parents=True)
    rows=read_report(dest)
    missing=[p for p in images if not (labels/(p.stem+".txt")).exists()]
    if not missing:
        print(f"{angle}: no missing labels")
        return
    window="Fixed-angle Val: click 4 corners | S save  R reset  N skip  Q quit"
    cv2.namedWindow(window,cv2.WINDOW_AUTOSIZE)
    count=0
    try:
        for number,path in enumerate(missing,1):
            cid=int(IMAGE.fullmatch(path.name).group(1))
            group,cls=lookup[cid]
            image=read_image(path)
            h,w=image.shape[:2]
            scale=min(1.,1000/w,760/h)
            display=cv2.resize(image,(round(w*scale),round(h*scale))) if scale<1 else image.copy()
            pts=[]
            dh,dw=display.shape[:2]

            def mouse(event,x,y,flags,param):
                if event==cv2.EVENT_LBUTTONDOWN and len(pts)<4:
                    pts.append((float(x)/scale,float(y)/scale))
            cv2.setMouseCallback(window,mouse)
            while True:
                vis=display.copy()
                for i,(x,y) in enumerate(pts):
                    cv2.circle(vis,(int(x*scale),int(y*scale)),5,(0,0,255),-1)
                    cv2.putText(vis,str(i+1),(int(x*scale)+8,int(y*scale)),
                                cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,255),2)
                if len(pts)>=2:
                    cv2.polylines(vis,[np.int32([[x*scale,y*scale] for x,y in pts])],
                                  len(pts)==4,(0,165,255),2)
                cv2.rectangle(vis,(0,0),(dw,58),(30,30,30),-1)
                cv2.putText(vis,f"{number}/{len(missing)} {group} {angle} | {len(pts)}/4 corners",
                            (8,22),cv2.FONT_HERSHEY_SIMPLEX,.54,(255,255,255),2)
                cv2.putText(vis,"S save / R reset / N skip / Q quit",(8,48),
                            cv2.FONT_HERSHEY_SIMPLEX,.48,(150,240,170),1)
                cv2.imshow(window,vis)
                key=cv2.waitKey(30)&0xFF
                if key in (ord("q"),27):
                    return
                if key==ord("n"):
                    break
                if key==ord("r"):
                    pts.clear()
                    continue
                if key!=ord("s") or len(pts)!=4:
                    continue
                quad=order_points(np.float32(pts))
                if not cv2.isContourConvex(quad) or cv2.contourArea(quad)<w*h*.001:
                    print("Invalid corners: press R and retry")
                    continue
                vis,box=preview(image,quad,f"{group} / {angle} / MANUAL")
                label=labels/(path.stem+".txt")
                if label.exists():
                    print(f"Refusing overwrite: {label}")
                    break
                save_image(previews/(path.stem+".jpg"),vis)
                label.write_text(str(cls)+" "+" ".join(f"{v:.6f}" for v in box)+"\n",
                                 encoding="utf-8")
                row=rows.get(path.name,{k:"" for k in FIELDS})
                row.update(image=path.name,card_id=f"{cid:03d}",group_id=group,
                           class_id=str(cls),status="MANUAL_REVIEW",
                           method="manual_four_corners",
                           corner_points_px=";".join(f"{x:.1f},{y:.1f}" for x,y in quad))
                rows[path.name]=row
                count+=1
                print("SAVED",path.name)
                # Save immediately, including when user quits mid-batch.
                write_report(dest,list(rows.values()))
                break
    finally:
        cv2.destroyAllWindows()
        print(f"{angle}: saved {count} manual labels")


def review(lookup):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    items=[]
    for angle in ANGLES:
        src,dest,labels,previews=paths_for(angle)
        report=read_report(dest)
        if not src.is_dir():
            items.append(f"<h2>{angle}: NO SOURCE FOLDER</h2>")
            continue
        images=sorted(p for p in src.iterdir() if p.suffix.lower() in EXTS)
        cards=[]
        for path in images:
            m=IMAGE.fullmatch(path.name)
            if m is None:
                continue
            cid=int(m.group(1))
            if cid not in lookup:
                continue
            preview_path=previews/(path.stem+".jpg")
            label=labels/(path.stem+".txt")
            has_label=label.is_file()
            status=report.get(path.name,{}).get("status","NO_REPORT")
            if status in ("REVIEW","MANUAL_REVIEW") and not has_label:
                status="MISSING_LABEL"
            image_ref=preview_path if preview_path.is_file() else path
            image_url=html.escape(image_ref.resolve().as_uri(),quote=True)
            original_url=html.escape(path.resolve().as_uri(),quote=True)
            card_class="warn" if not has_label or status.startswith(("FAIL","NO_REPORT","MISSING")) else ""
            cards.append(f'<article class="{card_class}"><a href="{original_url}">'
                         f'<img loading="lazy" src="{image_url}"></a>'
                         f'<div>{lookup[cid][0]} / {cid:03d} / {angle}</div>'
                         f'<strong>{html.escape(status)}</strong> '
                         f'{"LABEL" if has_label else "NO LABEL"}</article>')
        items.append(f"<section><h2>{angle} ({len(cards)}/20 images)</h2>"
                     f'<div class="grid">{"".join(cards)}</div></section>')
    doc="""<!doctype html><html lang="ja"><head><meta charset="utf-8">
    <title>Green20 fixed-angle Val review</title><style>
    body{font:15px system-ui,'Yu Gothic',sans-serif;margin:20px;background:#f4f6f8}
    section{margin:20px 0;padding:14px;background:white;border-radius:10px}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
    article{border:1px solid #ccc;border-radius:6px;padding:8px}
    .warn{background:#fff3e9;border-color:#e18d66}
    img{width:100%;height:150px;object-fit:contain}
    strong{font-size:12px} </style></head><body>
    <h1>緑20札・固定角度 Val アノテーション確認</h1>
    <p>全8方向、各20枚予定。REVIEW・MANUAL_REVIEWも学習前の目視確認が必要です。
    このHTMLはラベルの確認用で、承認操作はできません。</p>
    """+"".join(items)+"</body></html>"
    target=OUTPUT/"review_gallery.html"
    target.write_text(doc,encoding="utf-8")
    print("Gallery:",target)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--angle",choices=ANGLES,default=None,
                    help="Omit to process all 8 directions")
    mode=ap.add_mutually_exclusive_group()
    mode.add_argument("--fix-missing",action="store_true")
    mode.add_argument("--review",action="store_true")
    args=ap.parse_args()
    lookup=mappings()
    if args.review:
        review(lookup)
        return
    angles=[args.angle] if args.angle else ANGLES
    if args.fix_missing:
        for angle in angles:
            run_manual(angle,lookup)
    else:
        for angle in angles:
            result=run_auto(angle,lookup)
            print(f"{angle}: {dict(result)}")
        print("Run with --review to inspect the result, --fix-missing to repair failed images.")
    print("IMPORTANT: These fixed-angle photos are stored under train/h01_s01.")
    print("Confirm capture independence before assigning them to validation.")


if __name__=="__main__":
    main()
