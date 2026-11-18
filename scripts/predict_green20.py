"""YOLO inference with card number + kimariji on output image and CSV.

Example:
 uv run python scripts/predict_green20.py --model runs/detect/runs/green20/trial_01/weights/best.pt --source data/raw/green20/test/competition --imgsz 1280 --conf 0.25

Requires Pillow for Japanese image labels (usually included with Ultralytics).\nUse --labels-dir to write a separate *_gt.png with correct card IDs and prefixes.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO
from card_geometry import extract_candidates, assess, draw_checks, EXPECTED_RATIO
from prediction_filter import select_indices

ROOT=Path(__file__).resolve().parents[1]
METADATA=ROOT/"data/metadata/green20_cards.csv"


def select_font(size: int):
    from PIL import ImageFont
    candidates=[
        Path("C:/Windows/Fonts/meiryo.ttc"),
        Path("C:/Windows/Fonts/YuGothM.ttc"),
        Path("C:/Windows/Fonts/msgothic.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate),size)
    return None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--source",required=True,help="Image file or folder")
    parser.add_argument("--output",type=Path,default=ROOT/"runs/green20_labeled")
    parser.add_argument("--imgsz",type=int,default=1280)
    parser.add_argument("--conf",type=float,default=0.25)
    parser.add_argument("--device",default="0")
    parser.add_argument("--check-geometry",action="store_true",
                        help="Evaluate card corners against 52x73mm physical ratio")
    parser.add_argument("--ratio-tolerance",type=float,default=0.10)
    parser.add_argument("--min-geometry-iou",type=float,default=0.30)
    parser.add_argument("--max-cards",type=int,default=20,
                        help="Maximum predictions per image, not a target")
    parser.add_argument("--dedup-iou",type=float,default=0.55)
    parser.add_argument("--dedup-coverage",type=float,default=0.80)
    parser.add_argument("--labels-dir",type=Path,default=None,
                        help="YOLO ground-truth labels folder (save extra *_gt.png for validation)")
    args=parser.parse_args()
    if not (0 < args.ratio_tolerance < 1 and 0 < args.min_geometry_iou < 1):
        parser.error("Geometry tolerances must be between 0 and 1")
    if args.max_cards<1 or not (0<args.dedup_iou<1) or not (0<args.dedup_coverage<=1):
        parser.error("Invalid box deduplication settings")
    with METADATA.open(encoding="utf-8-sig",newline="") as f:
        cards=list(csv.DictReader(f))
    lookup={i:(str(row["card_id"]).zfill(3),row["decision_prefix"])
            for i,row in enumerate(cards)}
    if len(lookup)!=20:
        parser.error("Expected 20 classes in metadata")
    if not args.model.is_file():
        parser.error(f"Model not found: {args.model}")
    from PIL import Image,ImageDraw
    font=select_font(26)
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    model=YOLO(str(args.model))
    results=model.predict(source=args.source,imgsz=args.imgsz,conf=args.conf,
                          device=args.device,stream=True,verbose=False)
    rows=[]
    geometry_rows=[]
    for result in results:
        original=result.orig_img
        if original is None:
            continue
        image=Image.fromarray(cv2.cvtColor(original,cv2.COLOR_BGR2RGB))
        draw=ImageDraw.Draw(image)
        name=Path(result.path).name
        boxes=result.boxes
        geometry_candidates=extract_candidates(original) if args.check_geometry else []
        geometry_checks=[]
        if boxes is not None:
            raw_boxes=list(boxes)
            positions=[tuple(map(float,b.xyxy[0].tolist())) for b in raw_boxes]
            confidences=[float(b.conf.item()) for b in raw_boxes]
            kept=select_indices(positions,confidences,
                                max_cards=args.max_cards,
                                iou_threshold=args.dedup_iou,
                                coverage_threshold=args.dedup_coverage)
            print(f"{name}: raw={len(raw_boxes)}, kept={len(kept)}, "
                  f"removed={len(raw_boxes)-len(kept)}")
            for index in kept:
                box=raw_boxes[index]
                cid=int(box.cls.item())
                if cid not in lookup:
                    raise ValueError(f"Unexpected class ID: {cid}")
                card,prefix=lookup[cid]
                conf=float(box.conf.item())
                x0,y0,x1,y1=map(float,box.xyxy[0].tolist())
                label=f"{card} ({prefix}) {conf:.1%}"
                draw.rectangle((x0,y0,x1,y1),outline=(255,153,0),width=3)
                # Draw readable Japanese text using a CJK font.
                if font is not None:
                    tx,ty=int(x0),max(0,int(y0)-34)
                    bb=draw.textbbox((tx,ty),label,font=font)
                    draw.rectangle((bb[0]-2,bb[1]-2,bb[2]+3,bb[3]+3),fill=(0,0,0))
                    draw.text((tx,ty),label,font=font,fill=(255,255,255))
                if args.check_geometry:
                    check=assess((x0,y0,x1,y1),geometry_candidates,
                                 ratio_tolerance=args.ratio_tolerance,
                                 min_iou=args.min_geometry_iou)
                    geometry_checks.append(dict(card_id=card,bbox=(x0,y0,x1,y1),geometry=check))
                    corners=check["corners"]
                    geometry_rows.append(dict(
                        image=name,card_id=card,decision_prefix=prefix,
                        confidence=f"{conf:.5f}",geometry_status=check["status"],
                        expected_short_long_ratio=f"{EXPECTED_RATIO:.6f}",
                        measured_short_long_ratio=(
                            f'{check["ratio"]:.6f}' if check["ratio"] is not None else ""),
                        relative_ratio_error=(
                            f'{check["ratio_error"]:.6f}' if check["ratio_error"] is not None else ""),
                        candidate_bbox_iou=f'{check["overlap"]:.6f}',
                        corner_points_px=(
                            ";".join(f"{p[0]:.1f},{p[1]:.1f}" for p in corners)
                            if corners is not None else ""),
                        candidate_method=check["method"]))
                rows.append(dict(image=name,card_id=card,decision_prefix=prefix,
                                 confidence=f"{conf:.5f}",x0=round(x0,1),y0=round(y0,1),
                                 x1=round(x1,1),y1=round(y1,1)))
                print(f"{name}: {card} ({prefix}) {conf:.1%}")
        if args.check_geometry:
            geom_vis=draw_checks(original,geometry_checks)
            geom_file=out/(Path(name).stem+"_geometry.png")
            ok,encoded=cv2.imencode(".png",geom_vis)
            if not ok:
                raise OSError(f"Could not encode geometry preview: {geom_file}")
            encoded.tofile(str(geom_file))
            statuses=[r["geometry"]["status"] for r in geometry_checks]
            print(f"Geometry: {name}: OK={statuses.count('OK')} "
                  f"RATIO_CHECK={statuses.count('RATIO_CHECK')} "
                  f"NOT_FOUND={statuses.count('NOT_FOUND')}")
            print(f"Saved: {geom_file}")
        if args.labels_dir is not None:
            gt_path=args.labels_dir/(Path(name).stem+".txt")
            if not gt_path.is_file():
                raise FileNotFoundError(f"Ground-truth label missing: {gt_path}")
            gt_img=Image.fromarray(cv2.cvtColor(original,cv2.COLOR_BGR2RGB))
            gt_draw=ImageDraw.Draw(gt_img)
            hh,ww=original.shape[:2]
            for line in gt_path.read_text(encoding="utf-8").splitlines():
                fields=line.split()
                if len(fields)!=5:
                    raise ValueError(f"Invalid YOLO label in {gt_path}: {line}")
                cls=int(fields[0])
                if cls not in lookup:
                    raise ValueError(f"Unknown ground-truth class {cls}: {gt_path}")
                cx,cy,bw,bh=map(float,fields[1:])
                x0=(cx-bw/2)*ww
                y0=(cy-bh/2)*hh
                x1=(cx+bw/2)*ww
                y1=(cy+bh/2)*hh
                gt_draw.rectangle((x0,y0,x1,y1),outline=(0,220,80),width=3)
                if font is not None:
                    card,prefix=lookup[cls]
                    caption=f"GT {card} ({prefix})"
                    tx,ty=max(0,int(x0)),max(0,int(y0)-34)
                    rect=gt_draw.textbbox((tx,ty),caption,font=font)
                    gt_draw.rectangle((rect[0]-2,rect[1]-2,rect[2]+3,rect[3]+3),fill=(0,0,0))
                    gt_draw.text((tx,ty),caption,font=font,fill=(255,255,255))
            gt_target=out/(Path(name).stem+"_gt.png")
            gt_img.save(gt_target)
            print(f"Saved ground truth: {gt_target}")
        target=out/(Path(name).stem+"_pred.png")
        image.save(target)
        print(f"Saved: {target}")
    with (out/"predictions.csv").open("w",encoding="utf-8-sig",newline="") as f:
        fields=["image","card_id","decision_prefix","confidence","x0","y0","x1","y1"]
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved: {out/'predictions.csv'}")
    if args.check_geometry:
        geometry_csv=out/"geometry_report.csv"
        columns=["image","card_id","decision_prefix","confidence",
                 "geometry_status","expected_short_long_ratio",
                 "measured_short_long_ratio","relative_ratio_error",
                 "candidate_bbox_iou","corner_points_px","candidate_method"]
        with geometry_csv.open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=columns)
            writer.writeheader()
            writer.writerows(geometry_rows)
        print(f"Saved: {geometry_csv}")
        print("Geometry flags are diagnostic, not proof of correct class.")
    if font is None:
        print("WARNING: No Japanese font found. Japanese labels are in CSV/console only.")
        print("Install a CJK font, e.g. Windows Meiryo, to also draw decision prefixes.")


def run_with_timing_log():
    """Run inference and save one CSV record, including failures and interrupts."""
    import sys
    import time
    from datetime import datetime

    def now():
        return datetime.now().astimezone().isoformat(timespec="seconds")

    started_at = now()
    started_perf = time.perf_counter()
    log_dir = ROOT / "runs/experiment_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    log_path = log_dir / f"predict_{file_stamp}.csv"
    status = "running"
    error = ""
    try:
        main()
        status = "completed"
    except BaseException as exc:
        status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        finished_at = now()
        elapsed = round(time.perf_counter() - started_perf, 2)
        total = int(round(elapsed))
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        record = {
            "activity": "YOLO推論",
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "elapsed_hms": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            "elapsed_seconds": elapsed,
            "command": " ".join(sys.argv),
            "error": error,
        }
        try:
            with log_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(record))
                writer.writeheader()
                writer.writerow(record)
            print(f"Prediction timing log: {log_path}")
            print(f"Started: {started_at}")
            print(f"Finished: {finished_at}")
            print(f"Elapsed: {record['elapsed_hms']}")
        except OSError as log_exc:
            print(f"WARNING: Could not save inference timing log: {log_exc}", file=sys.stderr)


if __name__=="__main__":
    run_with_timing_log()
