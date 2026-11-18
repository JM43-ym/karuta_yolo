"""Annotate 2/3 touching cards using recorded left-to-right IDs.

Inputs: data/raw/green20/val/multi/{two_cards,three_cards}/{two,three}_N.png
Mapping: data/metadata/green20_val_layouts.csv
Outputs: data/annotations/green20_h03_multi_val/{labels,previews,report.csv}

Run: uv run python scripts/annotate_multi_val.py
Every output is provisional (REVIEW); inspect *all* previews before use.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import cv2
import numpy as np

from auto_annotate import candidate_rects, make_annotation, read_image, save_image

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "data/metadata/green20_val_layouts.csv"
SOURCE = ROOT / "data/raw/green20/val/multi"
OUTPUT = ROOT / "data/annotations/green20_h03_multi_val"


def overlap(a: np.ndarray, b: np.ndarray) -> float:
    ax0, ay0 = a.min(axis=0)
    ax1, ay1 = a.max(axis=0)
    bx0, by0 = b.min(axis=0)
    bx1, by1 = b.max(axis=0)
    area = max(0., min(ax1, bx1) - max(ax0, bx0)) * max(0., min(ay1, by1) - max(ay0, by0))
    denom = (ax1-ax0)*(ay1-ay0)+(bx1-bx0)*(by1-by0)-area
    return float(area / max(denom, 1.))


def locate(image: np.ndarray, expected: int, width_expansion: float, height_expansion: float):
    """Select aligned similarly sized white-face proposals without assuming isolated green borders."""
    proposals = candidate_rects(image, width_expansion, height_expansion)
    unique = []
    for score, corners, method in proposals:
        if all(overlap(corners, prev[1]) < 0.35 for prev in unique):
            unique.append((score, corners, method))
    # There can be several large-looking candidates from card text or glare.
    # Evaluate groups by horizontal alignment and equal area rather than only score.
    from itertools import combinations
    best = None
    for group in combinations(unique[:15], expected):
        boxes = [p[1] for p in group]
        widths = np.array([c[:,0].max()-c[:,0].min() for c in boxes])
        heights = np.array([c[:,1].max()-c[:,1].min() for c in boxes])
        centers = np.array([c.mean(axis=0) for c in boxes])
        if min(widths) <= 0 or min(heights) <= 0:
            continue
        if max(widths)/min(widths) > 1.65 or max(heights)/min(heights) > 1.65:
            continue
        if np.ptp(centers[:,1]) > max(heights)*0.5:
            continue
        ordered = sorted(group, key=lambda p: float(p[1][:,0].mean()))
        # reject heavily overlapping candidates
        if any(overlap(ordered[i][1],ordered[j][1]) > 0.10
               for i in range(expected) for j in range(i+1,expected)):
            continue
        # Prefer spatially adjacent cards and comparable white-face sizes.
        extent = max(centers[:,0])-min(centers[:,0])
        regularity = np.std(widths)/np.mean(widths) + np.std(heights)/np.mean(heights)
        rank = sum(p[0] for p in group) - regularity*4 - abs(extent/np.mean(widths)-(expected-1))*0.25
        if best is None or rank > best[0]:
            best = (rank, ordered)
    return (best[1] if best else None), unique


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=OUTPUT)
    ap.add_argument("--border-width", type=float, default=0.10)
    ap.add_argument("--border-height", type=float, default=0.06)
    args = ap.parse_args()
    if not (0 <= args.border_width <= .30 and 0 <= args.border_height <= .30):
        ap.error("Expansion must be in range 0..0.30")
    out = args.output.resolve()
    if out == SOURCE.resolve():
        ap.error("Do not overwrite raw photographs")
    for part in ("labels", "previews"):
        (out / part).mkdir(parents=True, exist_ok=True)
    with (ROOT / "data/metadata/green20_cards.csv").open(encoding="utf-8-sig",newline="") as f:
        classes = {int(row["card_id"]):i for i,row in enumerate(csv.DictReader(f))}
    with MAPPING.open(encoding="utf-8-sig", newline="") as f:
        records = list(csv.DictReader(f))
    if len(records) != 40 or len({r["filename"] for r in records}) != 40:
        raise ValueError("Expected exactly 40 distinct layouts in metadata")
    report = []
    for row in records:
        fname = row["filename"]
        if not re.fullmatch(r"(two|three)_\d+\.png",fname):
            raise ValueError(f"Unexpected filename: {fname}")
        prefix = fname.split("_")[0]
        expected = 2 if prefix == "two" else 3
        ids = [int(s) for s in row["card_ids_left_to_right"].split(";")]
        if len(ids) != expected or len(set(ids)) != expected or any(n not in classes for n in ids):
            raise ValueError(f"Invalid card sequence: {fname}: {ids}")
        path = SOURCE / (prefix + "_cards") / fname
        label_path = out / "labels" / (path.stem + ".txt")
        label_path.unlink(missing_ok=True)
        status, found = "", 0
        try:
            if not path.is_file():
                raise ValueError(f"Missing image: {path}")
            img = read_image(path)
            selected, possible = locate(img, expected, args.border_width, args.border_height)
            found = len(possible)
            vis = img.copy()
            if selected is None:
                for _,c,_ in possible:
                    cv2.polylines(vis,[c.astype(np.int32)],True,(0,0,255),2)
                status = "FAIL: could not isolate all card faces"
            else:
                lines=[]
                for ident,(_,corners,_) in zip(ids,selected):
                    xywh = make_annotation(img,corners)
                    if xywh is None:
                        raise ValueError("Invalid box")
                    lines.append(str(classes[ident])+" "+" ".join(f"{v:.6f}" for v in xywh))
                    cv2.polylines(vis,[corners.astype(np.int32)],True,(0,165,255),3)
                    x,y = corners.mean(axis=0)
                    cv2.putText(vis,f"{ident:03d}",(int(x)-25,int(y)),cv2.FONT_HERSHEY_SIMPLEX,0.9,(0,0,255),2)
                label_path.write_text("\n".join(lines)+"\n",encoding="utf-8")
                status = "REVIEW"
            scale = min(1.0, 1100/max(img.shape[:2]))
            if scale < 1:
                vis=cv2.resize(vis,(round(vis.shape[1]*scale),round(vis.shape[0]*scale)))
            save_image(out/"previews"/(path.stem+".jpg"),vis)
        except (OSError, ValueError, cv2.error) as exc:
            status=f"FAIL: {exc}"
        report.append(dict(filename=fname,card_ids_left_to_right=";".join(f"{n:03d}" for n in ids),
                           expected_cards=expected,candidates=found,status=status))
        print(f"{fname}: {status} ({found} candidates)")
    with (out/"report.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(report[0]))
        writer.writeheader()
        writer.writerows(report)
    ok=sum(row["status"]=="REVIEW" for row in report)
    print(f"\n{ok}/40 provisionally annotated. Review EVERY preview before dataset generation.")
    print("FAIL files need manual labeling or detector tuning; no label produced for them.")


if __name__=="__main__":
    main()
