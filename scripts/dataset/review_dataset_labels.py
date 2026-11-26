"""Create class-by-class HTML gallery of actual YOLO image/label pairs.

Usage:
  uv run --no-sync python scripts/dataset/review_dataset_labels.py --data data/datasets/green20_near_front_multi_val/data.yaml --split val
  uv run --no-sync python scripts/dataset/review_dataset_labels.py --data data/datasets/green20_near_front_multi_val/data.yaml --split train
Produces a standalone HTML file plus previews, without changing the dataset.
"""
from __future__ import annotations
import argparse
import csv
import html
import re
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT=Path(__file__).resolve().parents[2]
EXT={".png",".jpg",".jpeg",".bmp",".webp"}

def image_paths(spec, base):
    values=spec if isinstance(spec,list) else [spec]
    paths=[]
    for v in values:
        p=Path(str(v))
        if not p.is_absolute(): p=base/p
        if p.is_dir():
            paths.extend(x for x in p.rglob("*") if x.suffix.lower() in EXT)
        else:
            raise FileNotFoundError(f"Expected image directory: {p}")
    return sorted(paths)

def label_for(image):
    parts=list(image.parts)
    if "images" not in parts:
        raise ValueError(f"Dataset image is not under images/: {image}")
    parts[len(parts)-1-parts[::-1].index("images")]="labels"
    return Path(*parts).with_suffix(".txt")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--data",type=Path,required=True)
    parser.add_argument("--split",choices=("train","val"),default="val")
    parser.add_argument("--output",type=Path,default=None)
    parser.add_argument("--max-per-class",type=int,default=0,
                        help="0=all; positive integer limits displayed images per class")
    args=parser.parse_args()
    if args.max_per_class<0:parser.error("--max-per-class must be >=0")
    with args.data.open(encoding="utf-8-sig") as f:cfg=yaml.safe_load(f)
    base=Path(str(cfg.get("path",args.data.resolve().parent)))
    if not base.is_absolute():base=(args.data.resolve().parent/base).resolve()
    images=image_paths(cfg[args.split],base)
    classes=cfg["names"]
    if isinstance(classes,dict):
        names={int(i):str(v) for i,v in classes.items()}
    else:
        names={i:str(v) for i,v in enumerate(classes)}
    if len(names)!=20:raise ValueError("Expected 20 class names")
    out=(args.output or ROOT/"runs/label_reviews"/args.data.parent.name/args.split).resolve()
    # Keep thumbnails outside source dataset: no modification to images/labels.
    out.mkdir(parents=True,exist_ok=True)
    previews=out/"previews"
    previews.mkdir(exist_ok=True)
    by_class=defaultdict(list)
    failures=[]
    count=0
    for image in images:
        label=label_for(image)
        if not label.exists():
            failures.append(f"Missing label: {label}")
            continue
        entries=[]
        for row in label.read_text(encoding="utf-8-sig").splitlines():
            fields=row.split()
            if len(fields)!=5:raise ValueError(f"Malformed label: {label}: {row}")
            cls=int(fields[0])
            if cls not in names:raise ValueError(f"Unknown class {cls}: {label}")
            vals=[float(x) for x in fields[1:]]
            if any(not np.isfinite(x) or x<0 or x>1 for x in vals) or min(vals[2:])<=0:
                raise ValueError(f"Invalid bbox: {label}: {row}")
            entries.append((cls,vals))
        if not entries:
            failures.append(f"Empty label: {label}")
            continue
        arr=np.fromfile(str(image),dtype=np.uint8)
        original=cv2.imdecode(arr,cv2.IMREAD_COLOR)
        if original is None:
            failures.append(f"Cannot read image: {image}")
            continue
        h,w=original.shape[:2]
        scale=min(1.,700./max(h,w))
        vis=cv2.resize(original,(max(1,round(w*scale)),max(1,round(h*scale))))
        for cls,(cx,cy,bw,bh) in entries:
            x0=round((cx-bw/2)*w*scale);y0=round((cy-bh/2)*h*scale)
            x1=round((cx+bw/2)*w*scale);y1=round((cy+bh/2)*h*scale)
            cv2.rectangle(vis,(x0,y0),(x1,y1),(0,165,255),2)
            cv2.putText(vis,names[cls],(max(x0,0),max(y0-5,18)),
                        cv2.FONT_HERSHEY_SIMPLEX,.55,(0,255,255),2)
        # Prefix with split name to avoid collisions between datasets.
        preview=previews/(f"{count:05d}_"+image.stem+".jpg")
        ok,buffer=cv2.imencode(".jpg",vis,[cv2.IMWRITE_JPEG_QUALITY,86])
        if not ok:raise OSError(f"Could not encode preview: {preview}")
        buffer.tofile(str(preview))
        import os
        source_link=Path(os.path.relpath(image,out)).as_posix()
        view_link=Path(os.path.relpath(preview,out)).as_posix()
        for cls,_ in entries:
            by_class[cls].append((source_link,view_link,image.name,len(entries)))
        count+=1
    sections=[]
    for cls in sorted(names):
        items=by_class[cls]
        displayed=items if not args.max_per_class else items[:args.max_per_class]
        cards=[]
        for source,preview,name,total in displayed:
            cards.append(f'<article><a href="{html.escape(source,quote=True)}"><img loading="lazy" src="{html.escape(preview,quote=True)}"></a><small>{html.escape(name)}<br>画像内の札 {total}枚</small></article>')
        sections.append(f'<section id="c{cls}"><h2>クラス {cls} / 札 {html.escape(names[cls])} （{len(items)}画像）</h2><div class="grid">{"".join(cards)}</div></section>')
    index=" ".join(f'<a href="#c{c}">{html.escape(names[c])} ({len(by_class[c])})</a>' for c in sorted(names))
    failures_html="".join(f"<li>{html.escape(x)}</li>" for x in failures)
    page=f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>YOLO label review</title><style>
body{{font-family:system-ui,'Yu Gothic',sans-serif;background:#f4f6f8;color:#17202a;margin:20px}}
nav{{display:flex;gap:8px;flex-wrap:wrap}}nav a{{border:1px solid #ccc;padding:5px 8px;border-radius:6px;background:white}}
section{{background:white;padding:14px;margin:20px 0;border-radius:12px;border:1px solid #ddd}}
h2{{font-size:18px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}}
article{{border:1px solid #ddd;border-radius:8px;padding:6px;min-width:0}}
img{{width:100%;height:175px;object-fit:contain;background:#e8eaed}}
small{{overflow-wrap:anywhere;font-size:11px}}a{{color:#15609b}}
</style></head><body><h1>{html.escape(args.split)}：札番号ごとのラベル確認</h1>
<p>画像 {count}枚。1画像に複数札がある場合、それぞれの札番号の項目に同じ画像が表示されます。全bboxはオレンジ色。札番号はクラス定義に基づきます。</p>
<nav>{index}</nav><p>問題のある画像・ラベル：{len(failures)}</p><ul>{failures_html}</ul>
{''.join(sections)}</body></html>"""
    target=out/"label_gallery.html"
    target.write_text(page,encoding="utf-8")
    print(f"Images: {count}; issues: {len(failures)}; HTML: {target}")
    if failures:raise SystemExit("Some image/label pairs are missing or unreadable. Review the HTML.")

if __name__=="__main__":
    main()
