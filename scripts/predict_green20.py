"""YOLO inference with card number + kimariji on output image and CSV.

Example:
 uv run python scripts/predict_green20.py --model runs/detect/runs/green20/trial_01/weights/best.pt --source data/raw/green20/test/competition --imgsz 1280 --conf 0.25

Requires Pillow for Japanese image labels (usually included with Ultralytics).
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

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
    args=parser.parse_args()
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
    for result in results:
        original=result.orig_img
        if original is None:
            continue
        image=Image.fromarray(cv2.cvtColor(original,cv2.COLOR_BGR2RGB))
        draw=ImageDraw.Draw(image)
        name=Path(result.path).name
        boxes=result.boxes
        if boxes is not None:
            for box in boxes:
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
                rows.append(dict(image=name,card_id=card,decision_prefix=prefix,
                                 confidence=f"{conf:.5f}",x0=round(x0,1),y0=round(y0,1),
                                 x1=round(x1,1),y1=round(y1,1)))
                print(f"{name}: {card} ({prefix}) {conf:.1%}")
        target=out/(Path(name).stem+"_pred.png")
        image.save(target)
        print(f"Saved: {target}")
    with (out/"predictions.csv").open("w",encoding="utf-8-sig",newline="") as f:
        fields=["image","card_id","decision_prefix","confidence","x0","y0","x1","y1"]
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved: {out/'predictions.csv'}")
    if font is None:
        print("WARNING: No Japanese font found. Japanese labels are in CSV/console only.")
        print("Install a CJK font, e.g. Windows Meiryo, to also draw decision prefixes.")


if __name__=="__main__":
    main()
