"""Video-aware v4 annotation: green card detection + optical-flow recovery.

Run v4 for every color/direction after frame extraction. The script uses
video frames between a good anchor and a failed sample, tracks features
*inside the card* with LK flow, fits a RANSAC homography, and rejects
poorly supported tracks. All labels are provisional; never overwrite v1-v3.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from auto_annotate import make_annotation, read_image, save_image
from annotate_karuta_frames_v3 import (
    detect_green_quad, detect_fragmented_green, order_points, perspective_check
)

ROOT = Path(__file__).resolve().parents[1]
COLORS = ("green20", "blue20", "pink20", "yellow20", "orange20")
NAME = re.compile(r"^card_(\d{3})_(LR|FB)_h01_(s\d+)_f(\d{6})\.png$", re.I)
COLUMNS = ("image", "card_id", "group_id", "class_id", "status", "method",
           "score", "corner_points_px", "source_frame", "tracked_frames",
           "inliers", "median_error_px")


def valid_quad(quad, shape):
    h, w = shape[:2]
    if not np.isfinite(quad).all():
        return False
    quad = order_points(quad)
    if not cv2.isContourConvex(quad.astype(np.float32)):
        return False
    area = abs(cv2.contourArea(quad))
    if not .002*w*h <= area <= .42*w*h:
        return False
    if min(quad[:,0]) < 2 or min(quad[:,1]) < 2 or max(quad[:,0]) >= w-2 or max(quad[:,1]) >= h-2:
        return False
    short, long_side = sorted(cv2.minAreaRect(quad)[1])
    if short < 10 or not 1.05 <= long_side / short <= 3.9:
        return False
    center = quad.mean(axis=0)
    return np.linalg.norm((center-[w*.5,h*.5])/[w,h]) < .34


def step_flow(a, b, quad):
    """One short optical-flow step; homography estimated from card texture."""
    old = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    new = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    mask = np.zeros(old.shape, np.uint8)
    center = quad.mean(axis=0)
    inner = (center + (quad-center)*.88).astype(np.int32)
    cv2.fillConvexPoly(mask, inner, 255)
    pts = cv2.goodFeaturesToTrack(old, maxCorners=160, qualityLevel=.005,
                                  minDistance=4, mask=mask, blockSize=5)
    if pts is None or len(pts) < 8:
        return None
    opts = dict(winSize=(25,25), maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,30,.015))
    nxt, status, _ = cv2.calcOpticalFlowPyrLK(old,new,pts,None,**opts)
    if nxt is None:
        return None
    back, back_ok, _ = cv2.calcOpticalFlowPyrLK(new,old,nxt,None,**opts)
    if back is None:
        return None
    diff = np.linalg.norm(pts.reshape(-1,2)-back.reshape(-1,2),axis=1)
    good = (status.reshape(-1)>0)&(back_ok.reshape(-1)>0)&(diff<2.5)
    p0=pts.reshape(-1,2)[good]
    p1=nxt.reshape(-1,2)[good]
    if len(p0)<7:
        return None
    hom, inlier = cv2.findHomography(p0,p1,cv2.RANSAC,3.0)
    if hom is None or inlier is None:
        return None
    ok=inlier.reshape(-1).astype(bool)
    if np.count_nonzero(ok)<6 or np.mean(ok)<.52:
        return None
    repro=cv2.perspectiveTransform(p0[ok].reshape(-1,1,2),hom).reshape(-1,2)
    med=float(np.median(np.linalg.norm(repro-p1[ok],axis=1)))
    if not np.isfinite(med) or med>3.0:
        return None
    new_quad=cv2.perspectiveTransform(quad.reshape(-1,1,2).astype(np.float32),hom).reshape(4,2)
    new_quad=order_points(new_quad)
    if not valid_quad(new_quad,b.shape):
        return None
    return new_quad, int(np.count_nonzero(ok)), med


def track_video(path, start_frame, end_frame, start_quad, sample_step=1):
    """Track from an anchor over decoded frames, forwards or backwards."""
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    # For reverse travel, decode once and reverse the short interval.
    lo, hi=sorted((start_frame,end_frame))
    cap.set(cv2.CAP_PROP_POS_FRAMES,lo)
    decoded={}
    try:
        for idx in range(lo,hi+1):
            ok,im=cap.read()
            if not ok:
                return None
            if idx==lo or idx==hi or idx%sample_step==0:
                decoded[idx]=im
    finally:
        cap.release()
    order=sorted(decoded, reverse=end_frame<start_frame)
    if order[0]!=start_frame:
        order.insert(0,start_frame)
    if order[-1]!=end_frame:
        order.append(end_frame)
    if any(i not in decoded for i in order):
        return None
    quad=order_points(start_quad)
    worst=0.
    min_inliers=999
    prev=decoded[order[0]]
    for idx in order[1:]:
        now=decoded[idx]
        fit=step_flow(prev,now,quad)
        if fit is None:
            return None
        quad,n,err=fit
        min_inliers=min(min_inliers,n)
        worst=max(worst,err)
        prev=now
    return quad, min_inliers, worst


def make_result(path, img, quad, method, score, cid, group, direction,
                extras=None):
    xywh=make_annotation(img,quad)
    if xywh is None:
        raise ValueError("Invalid YOLO box")
    info=dict.fromkeys(COLUMNS,"")
    info.update(image=path.name,card_id=f"{cid:03d}",group_id=group,
                class_id=str(cid-1),status="REVIEW",method=method,
                score=f"{score:.4f}",
                corner_points_px=";".join(f"{x:.1f},{y:.1f}" for x,y in quad))
    if extras:
        info.update(extras)
    return info,xywh


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--color",choices=COLORS,required=True)
    ap.add_argument("--direction",choices=("LR","FB"),required=True)
    ap.add_argument("--session",default="s01")
    ap.add_argument("--max-track-frames",type=int,default=160)
    args=ap.parse_args()
    if args.max_track_frames<1 or not re.fullmatch(r"s\d+",args.session):
        ap.error("Invalid tracking range/session")

    metadata=ROOT/"data/metadata"/f"{args.color}_cards.csv"
    with metadata.open(encoding="utf-8-sig",newline="") as f:
        mapping=list(csv.DictReader(f))
    groups={int(r["card_id"]):r["group_id"] for r in mapping}
    # Video karuta_N belongs to the card whose group_id suffix is N.
    video_index={int(r["card_id"]):int(r["group_id"][1:]) for r in mapping}
    extracted=ROOT/"data/raw"/args.color/"train/single/oblique/extracted"/f"h01_{args.session}"/args.direction
    videos=ROOT/"data/raw"/args.color/"train/single/oblique/videos"/f"h01_{args.session}"/args.direction
    out=ROOT/"data/annotations/video_frames"/args.color/f"h01_{args.session}"/f"{args.direction}_v4"
    if not extracted.is_dir():
        ap.error(f"No extracted frames: {extracted}")
    paths=sorted(extracted.glob("*.png"))
    if not paths:
        ap.error(f"No images: {extracted}")
    for folder in (out/"labels",out/"previews",out/"rectified"):
        folder.mkdir(parents=True,exist_ok=True)

    items=defaultdict(list)
    for path in paths:
        m=NAME.fullmatch(path.name)
        if not m or m.group(2).upper()!=args.direction or m.group(3)!=args.session:
            print("Skipping unexpectedly named image:",path.name)
            continue
        cid=int(m.group(1))
        if cid not in groups:
            print("Skipping unknown card:",path.name)
            continue
        im=read_image(path)
        proposals=detect_green_quad(im,args.direction)
        if not proposals:
            proposals=detect_fragmented_green(im,args.direction)
        quad=None
        score=0.
        method=""
        if proposals:
            score,quad,method,_,_=proposals[0]
        items[cid].append(dict(path=path,idx=int(m.group(4)),img=im,
                               quad=quad,score=score,method=method))

    for cid,frames in items.items():
        frames.sort(key=lambda x:x["idx"])
        video=videos/f"karuta_{video_index[cid]:02d}_{args.direction}.avi"
        for item in frames:
            if item["quad"] is not None:
                continue
            if not video.is_file():
                item["method"]="FAIL: no source AVI for video tracking"
                continue
            anchors=sorted((x for x in frames if x["quad"] is not None),
                           key=lambda x:abs(x["idx"]-item["idx"]))
            result=None
            for anchor in anchors:
                dist=abs(anchor["idx"]-item["idx"])
                if dist>args.max_track_frames:
                    continue
                result=track_video(video,anchor["idx"],item["idx"],anchor["quad"])
                if result is not None:
                    item["quad"],ninliers,error=result
                    item["method"]="video_optical_flow_homography"
                    item["score"]=float(ninliers)
                    item["extras"]=dict(source_frame=str(anchor["idx"]),
                                        tracked_frames=str(dist),
                                        inliers=str(ninliers),
                                        median_error_px=f"{error:.2f}")
                    break
            if result is None:
                item["method"]="FAIL: no trustworthy video tracking"
        for item in frames:
            path=item["path"]
            img=item["img"]
            quad=item["quad"]
            label=out/"labels"/(path.stem+".txt")
            preview=out/"previews"/(path.stem+".jpg")
            rectified=out/"rectified"/(path.stem+".png")
            record=dict.fromkeys(COLUMNS,"")
            record.update(image=path.name,card_id=f"{cid:03d}",
                          group_id=groups[cid],class_id=str(cid-1))
            if label.exists():
                record["status"]="SKIPPED_EXISTING_LABEL"
            elif quad is None:
                record["status"]=item["method"]
                vis=img.copy()
                cv2.putText(vis,"NO RELIABLE QUAD - MANUAL LABEL NEEDED",
                            (10,38),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,255),2)
                if not preview.exists():
                    h,w=vis.shape[:2]
                    scale=min(1.,1100./max(h,w))
                    if scale<1:
                        vis=cv2.resize(vis,(round(w*scale),round(h*scale)))
                    save_image(preview,vis)
            else:
                try:
                    record,xywh=make_result(path,img,quad,item["method"],
                                            item["score"],cid,groups[cid],
                                            args.direction,item.get("extras"))
                    vis=img.copy()
                    cv2.polylines(vis,[quad.astype(np.int32)],True,(0,165,255),3)
                    h,w=img.shape[:2]
                    cx,cy,bw,bh=xywh
                    xa,ya=int((cx-bw/2)*w),int((cy-bh/2)*h)
                    xb,yb=int((cx+bw/2)*w),int((cy+bh/2)*h)
                    cv2.rectangle(vis,(xa,ya),(xb,yb),(255,210,0),2)
                    cv2.putText(vis,f"{groups[cid]} {cid:03d} {item['method']} REVIEW",
                                (10,38),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,0,255),2)
                    scale=min(1.,1100./max(h,w))
                    if scale<1:
                        vis=cv2.resize(vis,(round(w*scale),round(h*scale)))
                    if not preview.exists():
                        save_image(preview,vis)
                    if not rectified.exists():
                        tl,tr,br,bl=order_points(quad)
                        dest_size=(520,730) if args.direction=="LR" else (730,520)
                        tw,th=dest_size
                        corners=np.float32([[0,0],[tw-1,0],[tw-1,th-1],[0,th-1]])
                        warp=cv2.warpPerspective(img,cv2.getPerspectiveTransform(
                            np.float32([tl,tr,br,bl]),corners),(tw,th))
                        ok,data=cv2.imencode(".png",warp)
                        if ok:
                            data.tofile(str(rectified))
                    label.write_text(str(cid-1)+" "+" ".join(f"{v:.6f}" for v in xywh)+"\n",
                                     encoding="utf-8")
                except (ValueError,cv2.error,OSError) as err:
                    record["status"]="FAIL: "+str(err)
            item["record"]=record
            print(path.name,record["status"],record["method"])
    report=out/"annotation_report.csv"
    with report.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=COLUMNS)
        writer.writeheader()
        for cid in sorted(items):
            for item in items[cid]:
                writer.writerow(item["record"])
    print("Labels:",out/"labels")
    print("Gallery: run review_karuta_annotations.py --variant v4")
    print("All labels are REVIEW only; video-tracked labels must be checked.")


if __name__=="__main__":
    main()
