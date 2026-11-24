"""Click four corners to repair ONLY missing video-frame labels.

Shows only images missing labels from the primary video annotation pipeline.
Click TL/TR/BR/BL (or any clockwise/counterclockwise order), then S to save.
R resets the four points, N skips, Q/Esc exits. Existing labels untouched.

Example:
  uv run --no-sync python scripts/manual_fix_karuta_frames.py --color green20 --direction FB
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

import cv2
import numpy as np

from auto_annotate import read_image, save_image, make_annotation
from annotate_karuta_frames import order_points

ROOT = Path(__file__).resolve().parents[2]
COLORS = ("green20", "blue20", "pink20", "yellow20", "orange20")
PATTERN = re.compile(r"^card_(\d{3})_(LR|FB)_h01_(s\d+)_f\d{6}\.png$", re.I)
WINDOW = "Karuta: click 4 corners  |  S save  R reset  N skip  Q quit"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--color", required=True, choices=COLORS)
    ap.add_argument("--direction", required=True, choices=("LR", "FB"))
    ap.add_argument("--session", default="s01")
    ap.add_argument("--preview-width", type=int, default=1100)
    args = ap.parse_args()
    if not re.fullmatch(r"s\d+", args.session) or args.preview_width < 300:
        ap.error("Invalid --session or --preview-width")

    with (ROOT/"data/metadata"/f"{args.color}_cards.csv").open(
            encoding="utf-8-sig", newline="") as f:
        groups = {int(r["card_id"]): r["group_id"] for r in csv.DictReader(f)}
    src = ROOT/"data/raw"/args.color/"train/single/oblique/extracted"/f"h01_{args.session}"/args.direction
    out = ROOT/"data/annotations/video_frames"/args.color/f"h01_{args.session}"/f"{args.direction}_annotated"
    if not src.is_dir() or not out.is_dir():
        ap.error("Missing extracted images or annotation folder. Run annotate_karuta_frames.py first.")
    labels, previews, rectified = (out/"labels", out/"previews", out/"rectified")
    for folder in (labels, previews, rectified):
        folder.mkdir(parents=True, exist_ok=True)
    report = out/"annotation_report.csv"
    previous = {}
    fieldnames = []
    if report.exists():
        with report.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            previous = {row["image"]: row for row in reader}
    wanted = []
    for p in sorted(src.glob("*.png")):
        match = PATTERN.fullmatch(p.name)
        if match is None or match.group(2).upper() != args.direction or match.group(3) != args.session:
            continue
        if int(match.group(1)) not in groups:
            continue
        if not (labels/(p.stem+".txt")).exists():
            wanted.append((p,int(match.group(1))))
    if not wanted:
        print("All matched extracted images already have labels. Nothing to repair.")
        return

    print(f"{len(wanted)} images without a label. Click four corners of the GREEN OUTER EDGE.")
    print("Click in order around the card; S: save, R: reset, N: skip, Q/Esc: quit.")
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    changes = {}
    try:
        for number, (path,cid) in enumerate(wanted, 1):
            original = read_image(path)
            h,w=original.shape[:2]
            scale=min(1.,args.preview_width/w)
            view=cv2.resize(original,(round(w*scale),round(h*scale))) if scale<1 else original.copy()
            vh,vw=view.shape[:2]
            pts=[]

            def on_click(event,x,y,flags,param):
                if event == cv2.EVENT_LBUTTONDOWN and 0 <= x < vw and 0 <= y < vh and len(pts)<4:
                    pts.append((float(x)/scale,float(y)/scale))

            cv2.setMouseCallback(WINDOW,on_click)
            while True:
                vis=view.copy()
                for i,point in enumerate(pts):
                    x,y=round(point[0]*scale),round(point[1]*scale)
                    cv2.circle(vis,(x,y),5,(0,0,255),-1)
                    cv2.putText(vis,str(i+1),(x+8,y+8),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,255),2)
                if len(pts)>=2:
                    coords=np.array([(round(x*scale),round(y*scale)) for x,y in pts],np.int32)
                    cv2.polylines(vis,[coords],len(pts)==4,(0,165,255),2)
                msg=f"{number}/{len(wanted)} {groups[cid]} / {cid:03d} {args.direction} - {len(pts)}/4 corners"
                cv2.rectangle(vis,(0,0),(vw,64),(30,30,30),-1)
                cv2.putText(vis,msg,(8,24),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),2)
                cv2.putText(vis,"Click 4 corners | S save  R reset  N skip  Q quit",
                            (8,51),cv2.FONT_HERSHEY_SIMPLEX,.48,(120,230,180),1)
                cv2.imshow(WINDOW,vis)
                key=cv2.waitKey(30)&0xFF
                if key in (ord("q"),27):
                    print("Stopping. Previously saved corrections are preserved.")
                    return
                if key==ord("n"):
                    print("SKIP",path.name)
                    break
                if key==ord("r"):
                    pts.clear()
                    continue
                if key!=ord("s"):
                    continue
                if len(pts)!=4:
                    print("Click all FOUR outer corners before saving.")
                    continue
                quad=order_points(np.float32(pts))
                if not cv2.isContourConvex(quad):
                    print("Invalid quadrilateral; press R to retry.")
                    continue
                bbox=make_annotation(original,quad)
                if bbox is None or cv2.contourArea(quad)<h*w*.001:
                    print("Invalid/small box. Press R to retry.")
                    continue
                # Save to the selected version only and never replace an existing label.
                label=labels/(path.stem+".txt")
                if label.exists():
                    print("Existing label found; refusing to overwrite",label)
                    break
                corrected=original.copy()
                cv2.polylines(corrected,[quad.astype(np.int32)],True,(0,165,255),3)
                xc,yc,bw,bh=bbox
                cv2.rectangle(corrected,
                    (int((xc-bw/2)*w),int((yc-bh/2)*h)),
                    (int((xc+bw/2)*w),int((yc+bh/2)*h)),(255,210,0),2)
                cv2.putText(corrected,f"{groups[cid]} / {cid:03d} MANUAL_REVIEW",
                            (12,35),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,0,255),2)
                resize=min(1.,1100/max(h,w))
                if resize<1:
                    corrected=cv2.resize(corrected,(round(w*resize),round(h*resize)))
                save_image(previews/(path.stem+".jpg"),corrected)
                tw,th=((520,730) if args.direction=="LR" else (730,520))
                target=np.float32([[0,0],[tw-1,0],[tw-1,th-1],[0,th-1]])
                warped=cv2.warpPerspective(original,
                    cv2.getPerspectiveTransform(quad,target),(tw,th))
                ok,encoded=cv2.imencode(".png",warped)
                if not ok:
                    print("Failed to save rectified preview; try again.")
                    continue
                encoded.tofile(str(rectified/(path.stem+".png")))
                label.write_text(str(cid-1)+" "+" ".join(f"{z:.6f}" for z in bbox)+"\n",encoding="utf-8")
                row=previous.get(path.name,{"image":path.name})
                row.update(image=path.name,card_id=f"{cid:03d}",group_id=groups[cid],
                           class_id=str(cid-1),status="MANUAL_REVIEW",method="manual_four_corners",
                           corner_points_px=";".join(f"{x:.1f},{y:.1f}" for x,y in quad))
                changes[path.name]=row
                print("SAVED",path.name)
                break
    finally:
        cv2.destroyAllWindows()
        if changes:
            previous.update(changes)
            combined = list(dict.fromkeys(fieldnames +
                ["image","card_id","group_id","class_id","status","method","corner_points_px"]))
            with report.open("w",encoding="utf-8-sig",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=combined,extrasaction="ignore")
                writer.writeheader()
                writer.writerows(previous.values())
            print(f"Saved {len(changes)} manual corrections. Rebuild the gallery to view them.")


if __name__=="__main__":
    main()
