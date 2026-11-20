"""Create provisional YOLO annotations for extracted karuta video frames.

Detect the green outer border, handle perspective/partial borders, and create
preview and rectified images for review. No YOLO model is required.
Existing labels are never overwritten.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import cv2
import numpy as np
from auto_annotate import read_image, save_image, make_annotation

ROOT = Path(__file__).resolve().parents[1]
COLORS = ("green20", "blue20", "pink20", "yellow20", "orange20")
PATTERN = re.compile(r"^card_(\d{3})_(LR|FB)_h01_s\d+_f\d{6}\.png$", re.I)
FIELDS = ("image", "card_id", "group_id", "class_id", "status", "method",
          "score", "corner_points_px", "green_fraction", "center_distance",
          "perspective_check")


def order_points(points):
    """TL, TR, BR, BL for any convex four-corner polygon."""
    pts = np.asarray(points, np.float32).reshape(4, 2)
    center = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1]-center[1], pts[:, 0]-center[0])
    pts = pts[np.argsort(angles)]
    start = int(np.argmin(pts.sum(axis=1)))
    pts = np.roll(pts, -start, axis=0)
    # With image Y pointing down, TL->TR->BR->BL is positive shoelace.
    if cv2.contourArea(pts, oriented=True) < 0:
        pts = pts[[0, 3, 2, 1]]
    return pts.astype(np.float32)


def green_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Green border has measurable saturation, unlike neutral gray and white reflections.
    mask = cv2.inRange(hsv, (30, 26, 25), (96, 255, 255))
    hh, ww = mask.shape
    k = max(3, int(min(hh, ww) * .007) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def perspective_check(img, corners, direction):
    """Diagnostic only: rectification is NOT proof of physical 52:73 ratio."""
    pts = order_points(corners)
    # Image-aligned LH side lengths give a rough check for extreme degeneracy.
    edges = [float(np.linalg.norm(pts[(i+1)%4]-pts[i])) for i in range(4)]
    if min(edges) < 8 or max(edges)/min(edges) > 6:
        return "DEGENERATE"
    # Destination has true target side ratio; checking ratio AFTER enforcing it
    # would be tautological. Instead report the opposite-side foreshortening.
    opp = max(edges[0],edges[2])/max(1.,min(edges[0],edges[2]))
    opp2 = max(edges[1],edges[3])/max(1.,min(edges[1],edges[3]))
    return f"opposite_edges={opp:.2f},{opp2:.2f}"


def detect_green_quad(img, direction):
    height,width = img.shape[:2]
    # Restrict to the central region: the card was initially centered.
    # Generous ROI preserves perspective displacement during the sweep.
    x0,y0,x1,y1 = int(width*.12),int(height*.10),int(width*.88),int(height*.90)
    crop = img[y0:y1, x0:x1]
    mask = green_mask(crop)
    cnts,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    proposals = []
    img_area = width*height
    expected_center = np.array([width*.5,height*.5],dtype=np.float32)
    for cnt in cnts:
        if len(cnt) < 4:
            continue
        area = float(cv2.contourArea(cnt))
        if not (.003*img_area < area < .40*img_area):
            continue
        perimeter = cv2.arcLength(cnt,True)
        hull = cv2.convexHull(cnt)
        approx = cv2.approxPolyDP(hull, .022*cv2.arcLength(hull,True),True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            # A rotated rectangle fallback is a crude approximation only.
            box = cv2.boxPoints(cv2.minAreaRect(cnt)).astype(np.float32)
            method = "green_minarearect_approx"
        else:
            box = approx.reshape(4,2).astype(np.float32)
            method = "green_convex_quad"
        box[:,0] += x0
        box[:,1] += y0
        box = order_points(box)
        bx0,by0 = box.min(axis=0)
        bx1,by1 = box.max(axis=0)
        if bx0 <= 2 or by0 <= 2 or bx1 >= width-2 or by1 >= height-2:
            continue
        polygon_area = abs(cv2.contourArea(box))
        if not (.003*img_area < polygon_area < .42*img_area):
            continue
        center = box.mean(axis=0)
        center_distance = float(np.linalg.norm((center-expected_center)/[width,height]))
        # Very distant contours are often the fluorescent strip or unrelated objects.
        if center_distance > .30:
            continue
        # A card should have a roughly quadrilateral area, even as a trapezoid.
        fill = area/max(1.,polygon_area)
        if not .38 < fill < 1.35:
            continue
        rr=cv2.minAreaRect(box)
        short,long=sorted(rr[1])
        ratio=long/max(short,1.)
        if not 1.06 < ratio < 3.8:
            continue
        # Text/texture cue: card face should have noticeably darker strokes.
        poly_mask = np.zeros((height,width),dtype=np.uint8)
        cv2.fillConvexPoly(poly_mask,box.astype(np.int32),255)
        gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        inside = gray[poly_mask>0]
        dark_fraction = float(np.mean(inside<110)) if len(inside) else 0.
        if dark_fraction < .004:
            continue
        green_in_polygon = float(np.count_nonzero(mask)) / max(1.,mask.size)
        score = (2.0 * min(fill,1.0) + min(polygon_area/img_area,.20)*3.0
                 - 3.5*center_distance + min(dark_fraction,.1)*2)
        if method != "green_convex_quad":
            score -= .45
        proposals.append((score,box,method,green_in_polygon,center_distance))
    return sorted(proposals,key=lambda x:x[0],reverse=True)



def detect_fragmented_green(img, direction):
    """Additional proposals when green border is broken, preserving glare safety."""
    h, w = img.shape[:2]
    x0, y0, x1, y1 = int(w*.15), int(h*.13), int(w*.85), int(h*.87)
    roi = img[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    proposals = []
    for min_s in (26, 14):
        green = cv2.inRange(hsv, (28,min_s,20), (100,255,255))
        for radius in (.01, .025):
            k = max(3, int(min(roi.shape[:2])*radius) | 1)
            mask = cv2.morphologyEx(green, cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k,k)))
            contours,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                if cv2.contourArea(cnt) < w*h*.001:
                    continue
                hull = cv2.convexHull(cnt)
                approx = cv2.approxPolyDP(hull, .025*cv2.arcLength(hull,True), True)
                if len(approx)==4 and cv2.isContourConvex(approx):
                    quad=approx.reshape(4,2).astype(np.float32)
                    method="fragmented_green_quad"
                else:
                    quad=cv2.boxPoints(cv2.minAreaRect(cnt))
                    method="fragmented_green_rotated_rect"
                quad[:,0]+=x0
                quad[:,1]+=y0
                quad=order_points(quad)
                area=abs(cv2.contourArea(quad))
                if not .003*w*h<area<.35*w*h:
                    continue
                if np.any(quad[:,0]<3) or np.any(quad[:,0]>w-3) or np.any(quad[:,1]<3) or np.any(quad[:,1]>h-3):
                    continue
                distance=float(np.linalg.norm((quad.mean(axis=0)-[w/2,h/2])/[w,h]))
                if distance>.28:
                    continue
                short,long=sorted(cv2.minAreaRect(quad)[1])
                if not 1.1<long/max(short,1.)<3.5:
                    continue
                # Black text and bright white paper must both be present INSIDE
                # the polygon (not just a white, featureless fluorescent glare).
                center=quad.mean(axis=0)
                inner=(center+(quad-center)*.75).astype(np.int32)
                region=np.zeros((h,w),np.uint8)
                cv2.fillConvexPoly(region,inner,255)
                pixels=gray[region>0]
                if len(pixels)<80:
                    continue
                dark=float(np.mean(pixels<115))
                light=float(np.mean(pixels>145))
                if dark<.006 or light<.40:
                    continue
                score=light+min(dark,.10)*4 + area/(w*h)*3 - distance*4
                if method.endswith("rotated_rect"):
                    score-=.25
                proposals.append((score,quad,method,0.,distance))
    return sorted(proposals,key=lambda x:x[0],reverse=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--color",choices=COLORS,required=True)
    ap.add_argument("--direction",choices=("LR","FB"),required=True)
    ap.add_argument("--session",default="s01")
    args=ap.parse_args()
    if not re.fullmatch(r"s\d+",args.session):
        ap.error("Invalid session")
    with (ROOT/"data/metadata"/f"{args.color}_cards.csv").open(encoding="utf-8-sig",newline="") as f:
        lookup={int(r["card_id"]):r["group_id"] for r in csv.DictReader(f)}
    src=ROOT/"data/raw"/args.color/"train/single/oblique/extracted"/f"h01_{args.session}"/args.direction
    base=ROOT/"data/annotations/video_frames"/args.color/f"h01_{args.session}"
    out=base/f"{args.direction}_annotated"
    legacy=base/f"{args.direction}_v3"
    if legacy.exists() and not out.exists():
        legacy.rename(out)
        print(f"Migrated existing annotations: {legacy} -> {out}")
    elif legacy.exists() and out.exists():
        print(f"WARNING: old {legacy.name} still exists. Using {out.name}; review before deleting old folder.")
    if not src.is_dir():
        ap.error(f"Missing extraction folder: {src}")
    images=sorted(src.glob("*.png"))
    if not images:
        ap.error(f"No PNG frames in {src}")
    labels,previews,rectified=out/"labels",out/"previews",out/"rectified"
    for folder in (labels,previews,rectified):
        folder.mkdir(parents=True,exist_ok=True)
    rows=[]
    for path in images:
        record=dict.fromkeys(FIELDS,"")
        record["image"]=path.name
        label=labels/(path.stem+".txt")
        preview=previews/(path.stem+".jpg")
        try:
            match=PATTERN.fullmatch(path.name)
            if not match or match.group(2).upper()!=args.direction:
                raise ValueError("Unexpected image name or direction")
            cid=int(match.group(1))
            if cid not in lookup:
                raise ValueError("Card not in mapping CSV")
            record.update(card_id=f"{cid:03d}",group_id=lookup[cid],class_id=str(cid-1))
            if label.exists():
                record["status"]="SKIPPED_EXISTING_LABEL"
                # Build preview only if missing? Avoid overwriting reviewed preview.
                rows.append(record)
                continue
            img=read_image(path)
            proposals=detect_green_quad(img,args.direction)
            if not proposals:
                proposals=detect_fragmented_green(img,args.direction)
            if not proposals:
                record["status"]="FAIL: green border/text not confidently found"
                vis=img.copy()
                cv2.putText(vis,"NO RELIABLE CARD QUAD - MANUAL LABEL NEEDED",
                            (12,38),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,255),2)
            else:
                score,corners,method,green_frac,dist=proposals[0]
                xywh=make_annotation(img,corners)
                if xywh is None:
                    raise ValueError("Invalid bounding box")
                record.update(status="REVIEW",method=method,score=f"{score:.3f}",
                              green_fraction=f"{green_frac:.5f}",
                              center_distance=f"{dist:.4f}",
                              perspective_check=perspective_check(img,corners,args.direction),
                              corner_points_px=";".join(f"{x:.1f},{y:.1f}" for x,y in corners))
                vis=img.copy()
                cv2.polylines(vis,[corners.astype(np.int32)],True,(0,165,255),3)
                h,w=img.shape[:2]
                cx,cy,bw,bh=xywh
                xa,ya=int((cx-bw/2)*w),int((cy-bh/2)*h)
                xb,yb=int((cx+bw/2)*w),int((cy+bh/2)*h)
                cv2.rectangle(vis,(xa,ya),(xb,yb),(255,210,0),2)
                cv2.putText(vis,f"{lookup[cid]} / {cid:03d} / {method} / REVIEW",
                            (12,38),cv2.FONT_HERSHEY_SIMPLEX,.62,(0,0,255),2)
                # A diagnostic rectified view of the estimated four corners.
                # Width:height is an ASSUMED output shape, not measured evidence
                # that the proposal is geometrically correct.
                quad=order_points(corners)
                target_w,target_h=((520,730) if args.direction=="LR" else (730,520))
                destination=np.float32([[0,0],[target_w-1,0],
                                        [target_w-1,target_h-1],[0,target_h-1]])
                mat=cv2.getPerspectiveTransform(quad,destination)
                warp=cv2.warpPerspective(img,mat,(target_w,target_h))
                warp_path=rectified/(path.stem+".png")
                if not warp_path.exists():
                    ok,encoded=cv2.imencode(".png",warp)
                    if not ok:
                        raise ValueError("Failed encoding rectified preview")
                    encoded.tofile(str(warp_path))
            hh,ww=vis.shape[:2]
            shrink=min(1.,1100/max(hh,ww))
            if shrink<1:
                vis=cv2.resize(vis,(round(ww*shrink),round(hh*shrink)))
            save_image(preview,vis)
            if proposals:
                # Write label only after preview was written successfully.
                label.write_text(f"{cid-1} "+" ".join(f"{v:.6f}" for v in xywh)+"\n",encoding="utf-8")
        except (ValueError,OSError,cv2.error) as exc:
            record["status"]="FAIL: "+str(exc)
        rows.append(record)
        print(path.name,record["status"])
    report=out/"annotation_report.csv"
    with report.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Labels: {labels}\nPreviews: {previews}\nReport: {report}")
    print("All labels are provisional. REVIEW every preview before training.")


if __name__=="__main__":
    main()
