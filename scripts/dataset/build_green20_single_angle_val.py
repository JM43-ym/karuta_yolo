"""Build green20 single-card Val (Top + F30/B30/L30/R30), reusing existing Train.

Default: check only. Never modify original images, annotations, or source dataset.
The fixed-angle photos are stored under raw/.../train/... despite their _s02
names. Their actual capture independence MUST be checked by the researcher.
"""
from __future__ import annotations

import argparse
import csv
import math
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DATASET = ROOT/"data/datasets/green20_near_front_multi_val"
OUTPUT = ROOT/"data/datasets/green20_near_front_single_angle_val"
RAW = ROOT/"data/raw/green20"
ANN = ROOT/"data/annotations/green20"
ANGLES = ("F30","B30","L30","R30")
EXTS = {".png",".jpg",".jpeg"}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def check_box(path, expected):
    if not path.is_file():
        raise FileNotFoundError(f"Missing label: {path}")
    lines = [line.split() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(lines) != 1 or len(lines[0]) != 5 or int(lines[0][0]) != expected:
        raise ValueError(f"Expected one valid label with class {expected}: {path}")
    xywh = list(map(float,lines[0][1:]))
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in xywh) or min(xywh[2:]) <= 0:
        raise ValueError(f"Invalid bounding box: {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-dataset",type=Path,default=SOURCE_DATASET)
    ap.add_argument("--output",type=Path,default=OUTPUT)
    ap.add_argument("--build",action="store_true")
    ap.add_argument("--confirm-independent-val",action="store_true",
                    help="Confirm angle photos are independent captures from Train's top and video frames")
    args = ap.parse_args()

    src = args.source_dataset.resolve()
    out = args.output.resolve()
    yaml_src = src/"data.yaml"
    if not yaml_src.is_file():
        ap.error(f"Existing dataset is missing: {yaml_src}")
    with yaml_src.open(encoding="utf-8-sig") as f:
        config = yaml.safe_load(f)
    training_images = src/"images/train"
    training_labels = src/"labels/train"
    if not training_images.is_dir() or not training_labels.is_dir():
        ap.error(f"Missing Train images or labels: {src}")
    ntrain = sum(1 for p in training_images.iterdir() if p.suffix.lower() in EXTS)
    nlabels = sum(1 for p in training_labels.iterdir() if p.suffix.lower()==".txt")
    if ntrain!=8520 or nlabels!=8520:
        ap.error(f"Expected existing Train 8520 pairs; images={ntrain}, labels={nlabels}")

    card_rows = sorted(read_csv(ROOT/"data/metadata/green20_cards.csv"),
                       key=lambda r:r["group_id"])
    mapping = {int(r["card_id"]):i for i,r in enumerate(card_rows)}
    if len(card_rows)!=20 or len(mapping)!=20:
        ap.error("Expected 20 distinct green classes")
    names = [f"{int(row['card_id']):03d}" for row in card_rows]
    if [str(config["names"][i]) if isinstance(config["names"],dict)
        else str(config["names"][i]) for i in range(20)] != names:
        ap.error("Source dataset uses a different class mapping")

    source_paths = []
    # Top Val is copied unchanged from the existing dataset to preserve exact
    # labels, not reannotated or augmented.
    current_val = src/"images/val"
    current_labels = src/"labels/val"
    top_images = sorted(p for p in current_val.glob("top_card_*") if p.suffix.lower() in EXTS)
    if len(top_images)!=20:
        ap.error(f"Expected 20 existing top_... Val images, got {len(top_images)}")
    for p in top_images:
        import re
        match = re.fullmatch(r"top_card_(\d{3})_top_h(01|03)_s02",p.stem)
        if match is None:
            ap.error(f"Unexpected top image: {p.name}")
        ident = int(match.group(1))
        if ident not in mapping:
            ap.error(f"Unknown card in top Val: {p.name}")
        label = current_labels/(p.stem+".txt")
        check_box(label,mapping[ident])
        source_paths.append((p,label,p.name))

    for angle in ANGLES:
        folder=RAW/"train/single/oblique/h01_s01"/angle
        labels=ANN/"green20_fixed_angle_val"/angle/"labels"
        images=sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTS) if folder.is_dir() else []
        if len(images)!=20:
            ap.error(f"Expected 20 {angle} images, got {len(images)}: {folder}")
        seen=set()
        for p in images:
            import re
            match=re.fullmatch(r"card_(\d{3})_"+angle+r"_s02",p.stem)
            if match is None:
                ap.error(f"Unexpected fixed-angle filename: {p.name}")
            ident=int(match.group(1))
            if ident not in mapping or ident in seen:
                ap.error(f"Invalid or duplicate card: {p.name}")
            seen.add(ident)
            label=labels/(p.stem+".txt")
            check_box(label,mapping[ident])
            # Prefix prevents any collision with top Val.
            source_paths.append((p,label,"fixed_"+p.name))
        if seen!=set(mapping):
            ap.error(f"Missing cards in {angle}: {set(mapping)-seen}")

    if len(source_paths)!=100 or len({name for _,_,name in source_paths})!=100:
        ap.error("Expected 100 distinct single-card image/label pairs")
    print("Validated: existing Train = 8520, Val = Top 20 + F30/B30/L30/R30 80")
    print("Val: 100 images, 100 instances, one per class per angle (5 per class)")
    print("Source fixed-angle path is under RAW/train: independently verify capture/session separation.")
    if not args.build:
        print("CHECK ONLY: no output created. Use --build --confirm-independent-val after visual inspection.")
        return
    if not args.confirm_independent_val:
        ap.error("--build requires --confirm-independent-val")
    if out.exists():
        ap.error(f"Refusing to overwrite existing output: {out}")
    if out==ROOT or out==src or RAW in out.parents or ANN in out.parents:
        ap.error(f"Unsafe output path: {out}")

    (out/"images/val").mkdir(parents=True)
    (out/"labels/val").mkdir(parents=True)
    for photo,label,name in source_paths:
        shutil.copy2(photo,out/"images/val"/name)
        shutil.copy2(label,out/"labels/val"/(Path(name).stem+".txt"))
    yaml_lines=[f"path: '{out.as_posix()}'",
                f"train: '{training_images.as_posix()}'",
                "val: images/val","nc: 20","names:"]
    yaml_lines += [f"  {i}: '{cid}'" for i,cid in enumerate(names)]
    (out/"data.yaml").write_text("\n".join(yaml_lines)+"\n",encoding="utf-8")
    with (out/"source_manifest.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.writer(f)
        writer.writerow(["output_image","original_image","original_label"])
        writer.writerows((name,str(p),str(label)) for p,label,name in source_paths)
    print(f"READY: {out/'data.yaml'}")
    print("Existing Train was linked through an absolute path; no Train image duplication.")


if __name__=="__main__":
    main()
