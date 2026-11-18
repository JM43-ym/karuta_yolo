"""Inspect YOLO dataset image and labeled object counts without loading images."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
import yaml

EXTS={".png",".jpg",".jpeg",".bmp",".tif",".tiff",".webp"}

def _paths(spec, base: Path):
    if isinstance(spec, list):
        return [p for s in spec for p in _paths(s,base)]
    path=Path(str(spec))
    if not path.is_absolute():
        path=base/path
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in EXTS)
    if path.is_file() and path.suffix.lower()==".txt":
        entries=[]
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line=line.strip()
            if not line: continue
            item=Path(line)
            entries.append((path.parent/item).resolve() if not item.is_absolute() else item)
        return entries
    raise FileNotFoundError(path)

def inventory(data_yaml:Path)->dict:
    data_yaml=data_yaml.resolve()
    with data_yaml.open(encoding="utf-8-sig") as f:
        cfg=yaml.safe_load(f)
    base=Path(str(cfg.get("path",data_yaml.parent)))
    if not base.is_absolute():
        base=(data_yaml.parent/base).resolve()
    result={"data_yaml":str(data_yaml),"splits":{}}
    for split in ("train","val","test"):
        if split not in cfg:continue
        images=_paths(cfg[split],base)
        by_group=Counter()
        by_class=Counter()
        count=0
        missing=[]
        for img in images:
            stem=img.stem
            if split=="train":
                group=next((h for h in ("h01","h02","h03") if f"_top_{h}_" in stem),"other")
            elif stem.startswith("two_"):
                group="two_cards"
            elif stem.startswith("three_"):
                group="three_cards"
            else:group="single_cards"
            by_group[group]+=1
            # Standard Ultralytics images/<split> -> labels/<split>.
            parts=list(img.parts)
            if "images" in parts:
                idx=len(parts)-1-parts[::-1].index("images")
                parts[idx]="labels"
                label=Path(*parts).with_suffix(".txt")
            else:
                label=img.with_suffix(".txt")
            if not label.exists():
                missing.append(str(label));continue
            for line in label.read_text(encoding="utf-8-sig").splitlines():
                tokens=line.strip().split()
                if not tokens:continue
                if len(tokens)<5:raise ValueError(f"Malformed label: {label}")
                by_class[tokens[0]]+=1
                count+=1
        result["splits"][split]={"images":len(images),"instances":count,
            "by_group":dict(sorted(by_group.items())),
            "by_class":dict(sorted(by_class.items(),key=lambda x:int(x[0]))),
            "missing_labels":len(missing)}
        if missing:raise FileNotFoundError(f"{len(missing)} missing labels, first: {missing[0]}")
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--data",type=Path,default=Path(__file__).resolve().parents[1]/"data/datasets/green20_v4/data.yaml")
    args=parser.parse_args()
    print(json.dumps(inventory(args.data),ensure_ascii=False,indent=2))
