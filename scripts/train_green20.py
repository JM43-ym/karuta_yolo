"""Train YOLO with upright-only augmentation and write reproducible experiment log.

Example:
 uv run python scripts/train_green20.py --epochs 30 --batch 8 --imgsz 640 --name trial_04

Log: runs/experiment_logs/<experiment>_<date>.json
Normal Ultralytics outputs (args.yaml, results.csv, best.pt) stay in run directory.
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import torch
import ultralytics
from ultralytics import YOLO

ROOT=Path(__file__).resolve().parents[1]


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",type=Path,default=ROOT/"data/datasets/green20_v4/data.yaml")
    ap.add_argument("--model",default="yolo11n.pt")
    ap.add_argument("--epochs",type=int,default=30)
    ap.add_argument("--batch",type=int,default=8)
    ap.add_argument("--imgsz",type=int,default=640)
    ap.add_argument("--device",default="0")
    ap.add_argument("--workers",type=int,default=0)
    ap.add_argument("--name",default="trial_04")
    args=ap.parse_args()
    data=args.data.resolve()
    if not data.is_file():
        ap.error(f"Missing data.yaml: {data}")
    if args.epochs<1 or args.batch<1 or args.imgsz<32:
        ap.error("Invalid epochs, batch or imgsz")
    run_project=ROOT/"runs/green20"
    log_dir=ROOT/"runs/experiment_logs"
    log_dir.mkdir(parents=True,exist_ok=True)
    log_file=log_dir/(f"{args.name}_{datetime.now().astimezone():%Y%m%d_%H%M%S}.json")
    params=dict(model=args.model,data=str(data),epochs=args.epochs,batch=args.batch,
                imgsz=args.imgsz,device=args.device,workers=args.workers,
                project=str(run_project),name=args.name,
                fliplr=0.0,flipud=0.0,degrees=0.0,shear=0.0,perspective=0.0,
                mosaic=0.0,mixup=0.0,copy_paste=0.0)
    record=dict(status="running",started_at=timestamp(),parameters=params,
                python=sys.version.split()[0],torch=torch.__version__,
                cuda=torch.version.cuda,ultralytics=ultralytics.__version__,
                platform=platform.platform())
    log_file.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    start=time.perf_counter()
    model=None
    try:
        model=YOLO(args.model)
        model.train(data=str(data),epochs=args.epochs,batch=args.batch,
                    imgsz=args.imgsz,device=args.device,workers=args.workers,
                    project=str(run_project),name=args.name,exist_ok=False,
                    fliplr=0.0,flipud=0.0,degrees=0.0,
                    shear=0.0,perspective=0.0,mosaic=0.0,
                    mixup=0.0,copy_paste=0.0)
        record["status"]="completed"
        metrics=getattr(model,"metrics",None)
        if metrics is not None and getattr(metrics,"results_dict",None) is not None:
            record["metrics"]={k:float(v) for k,v in metrics.results_dict.items()}
    except BaseException as exc:
        record["status"]="interrupted" if isinstance(exc,KeyboardInterrupt) else "failed"
        record["error"]=f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record["finished_at"]=timestamp()
        record["elapsed_seconds"]=round(time.perf_counter()-start,2)
        trainer=getattr(model,"trainer",None) if model is not None else None
        if trainer is not None and getattr(trainer,"save_dir",None) is not None:
            run_dir=Path(trainer.save_dir)
            record["run_dir"]=str(run_dir)
            csv_path=run_dir/"results.csv"
            if csv_path.is_file():
                try:
                    with csv_path.open(encoding="utf-8-sig",newline="") as f:
                        rows=list(csv.DictReader(f))
                    if rows:
                        record["last_epoch_metrics"]={k.strip():v for k,v in rows[-1].items()}
                        record["recorded_epochs"]=len(rows)
                except (OSError,ValueError) as exc:
                    record["results_csv_warning"]=str(exc)
        log_file.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"Experiment log: {log_file}")
        if record.get("run_dir"):
            print(f"Ultralytics run: {record['run_dir']}")


if __name__=="__main__":
    main()
