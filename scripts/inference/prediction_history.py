"""Maintain one CSV table for YOLO inference runs.

Legacy predict_*.csv files can be imported without running inference again.
Legacy files are deleted only after the consolidated CSV is successfully written
and checked; use --keep-legacy to retain them.

Run: uv run python scripts/prediction_history.py
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_SCRIPTS_DIR = _Path(__file__).resolve().parents[2]
if str(_SCRIPTS_DIR) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS_DIR))


import argparse
import csv
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "runs/experiment_logs"
HISTORY = LOG_DIR / "prediction_history.csv"

FIELDS = [
    "run_id", "activity", "status", "started_at", "finished_at",
    "elapsed_hms", "elapsed_seconds", "model", "source", "output",
    "imgsz", "conf", "geometry_enabled", "max_cards", "command", "error",
]


def load_history() -> list[dict[str, str]]:
    if not HISTORY.is_file():
        return []
    with HISTORY.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_history(rows: list[dict[str, str]]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(FIELDS + [key for row in rows for key in row]))
    # Write into a temporary file and atomically replace the CSV.
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="",
            prefix=".prediction_history_", suffix=".tmp",
            dir=LOG_DIR, delete=False
        ) as f:
            tmp_path = Path(f.name)
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, HISTORY)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def append_record(record: dict[str, object]) -> None:
    rows = load_history()
    run_id = str(record["run_id"])
    if any(row.get("run_id") == run_id for row in rows):
        raise ValueError(f"Inference run already recorded: {run_id}")
    rows.append({k: str(v) if v is not None else "" for k, v in record.items()})
    write_history(rows)


def import_legacy(*, keep_legacy: bool = False) -> tuple[int, int]:
    """Merge old one-file-per-inference logs; return (imported, duplicates)."""
    files = sorted(LOG_DIR.glob("predict_*.csv"))
    rows = load_history()
    known = {row.get("run_id") for row in rows}
    imported = 0
    duplicates = 0
    completed_files = []
    for path in files:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            legacy = list(csv.DictReader(f))
        if len(legacy) != 1:
            raise ValueError(f"Expected one record in {path}; found {len(legacy)}. Nothing deleted.")
        row = dict(legacy[0])
        run_id = path.stem
        if run_id in known:
            duplicates += 1
        else:
            row["run_id"] = run_id
            rows.append(row)
            known.add(run_id)
            imported += 1
        completed_files.append(path)

    if files:
        write_history(rows)
        # Verify every ID before any deletion.
        saved = {row.get("run_id") for row in load_history()}
        if not known.issubset(saved):
            raise RuntimeError("CSV verification failed; legacy logs were preserved.")
        if not keep_legacy:
            for path in completed_files:
                path.unlink()
    return imported, duplicates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-legacy", action="store_true",
                        help="Do not delete old predict_*.csv files after consolidation")
    args = parser.parse_args()
    imported, duplicates = import_legacy(keep_legacy=args.keep_legacy)
    print(f"Imported: {imported}, already listed: {duplicates}")
    print(f"Prediction history: {HISTORY}")
    if not args.keep_legacy:
        print("Legacy predict_*.csv files removed after the combined CSV was verified.")
    print(f"Total inference runs in index: {len(load_history())}")


if __name__ == "__main__":
    main()
