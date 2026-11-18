"""Compare YOLO predictions with card-shaped quadrilateral candidates.

The physical card is 52 x 73 mm. Rotation-invariant geometry is measured
from four inferred corners, NOT from YOLO's axis-aligned bbox. White-face
contour proposals are expanded to approximate the outer green border.

The geometry check is diagnostic only: it does NOT change detection or class.
"""
from __future__ import annotations

from dataclasses import dataclass
import cv2
import numpy as np
from auto_annotate import candidate_rects

CARD_SHORT_MM=52.0
CARD_LONG_MM=73.0
EXPECTED_RATIO=CARD_SHORT_MM/CARD_LONG_MM


def aabb(points:np.ndarray)->tuple[float,float,float,float]:
    lo=points.min(axis=0); hi=points.max(axis=0)
    return float(lo[0]),float(lo[1]),float(hi[0]),float(hi[1])


def iou(box1,box2)->float:
    a,b,c,d=box1; e,f,g,h=box2
    area=max(0,min(c,g)-max(a,e))*max(0,min(d,h)-max(b,f))
    union=max(0,c-a)*max(0,d-b)+max(0,g-e)*max(0,h-f)-area
    return area/union if union>0 else 0.0


def quad_ratio(pts:np.ndarray)->float:
    # Opposite edges averaged to reduce small corner-estimation errors.
    edges=[float(np.linalg.norm(pts[(i+1)%4]-pts[i])) for i in range(4)]
    sides=[(edges[0]+edges[2])/2,(edges[1]+edges[3])/2]
    return min(sides)/max(max(sides),1e-9)


@dataclass
class Candidate:
    corners:np.ndarray
    ratio:float
    score:float
    method:str

def extract_candidates(image:np.ndarray)->list[Candidate]:
    proposed=candidate_rects(image,0.10,0.06)
    selected=[]
    for score,corners,method in proposed:
        # The source detector proposes both bright and Otsu candidates.
        if all(iou(aabb(corners),aabb(c.corners))<0.65 for c in selected):
            selected.append(Candidate(corners,quad_ratio(corners),score,method))
    return selected


def assess(pred_box,candidates:list[Candidate],ratio_tolerance:float=0.15,
           min_iou:float=0.45):
    # An independent shape contour must align with the YOLO prediction.
    ranked=sorted(((iou(pred_box,aabb(c.corners)),c) for c in candidates),
                  key=lambda pair:pair[0],reverse=True)
    if not ranked or ranked[0][0]<min_iou:
        return dict(status="NOT_FOUND",ratio=None,ratio_error=None,
                    overlap=ranked[0][0] if ranked else 0.0,corners=None,
                    method="")
    overlap,c=ranked[0]
    error=abs(c.ratio-EXPECTED_RATIO)/EXPECTED_RATIO
    status="OK" if error<=ratio_tolerance else "RATIO_CHECK"
    return dict(status=status,ratio=c.ratio,ratio_error=error,
                overlap=overlap,corners=c.corners,method=c.method)


def draw_checks(original:np.ndarray,checks:list[dict])->np.ndarray:
    visual=original.copy()
    for entry in checks:
        check=entry["geometry"]
        x0,y0,x1,y1=entry["bbox"]
        color={"OK":(45,190,60),"RATIO_CHECK":(0,155,255),
               "NOT_FOUND":(0,0,255)}[check["status"]]
        cv2.rectangle(visual,(int(x0),int(y0)),(int(x1),int(y1)),color,2)
        if check["corners"] is not None:
            cv2.polylines(visual,[check["corners"].astype(np.int32)],True,color,3)
            for n,point in enumerate(check["corners"]):
                cv2.circle(visual,tuple(point.astype(int)),4,color,-1)
        label=f'{entry["card_id"]}: {check["status"]}'
        if check["ratio"] is not None:
            label+=f' r={check["ratio"]:.3f}'
        cv2.putText(visual,label,(int(x0),max(18,int(y0)-7)),
                    cv2.FONT_HERSHEY_SIMPLEX,0.55,color,2,cv2.LINE_AA)
    return visual
