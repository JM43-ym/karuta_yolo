"""Check moved Python files, compatibility wrappers and basic syntax.

Only uses Python stdlib. Does not start camera, load CUDA, or modify datasets.
"""
from __future__ import annotations
import ast
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
MOVED = {
    "annotation": ["auto_annotate", "annotate_karuta_frames", "annotate_green20_val_angles",
                   "annotate_multi_val", "manual_fix_karuta_frames", "review_karuta_annotations"],
    "renaming": ["rename_green20", "rename_green20_val_angles"],
    "capture": ["extract_karuta_frames"],
    "gui": ["capture_karuta_video"],
    "dataset": ["generate_rotations", "build_green20_v3", "build_green20_v4",
                "build_green20_video_augmented", "dataset_inventory", "check_green20_paths"],
    "training": ["train_green20"],
    "inference": ["predict_green20", "card_geometry", "prediction_filter", "prediction_history"],
}

def main():
    errors = []
    checked = 0
    for category, names in MOVED.items():
        for name in names:
            actual = SCRIPTS / category / f"{name}.py"
            compat = SCRIPTS / f"{name}.py"
            for file in (actual, compat):
                if not file.is_file():
                    errors.append(f"Missing: {file}")
                    continue
                source = file.read_text(encoding="utf-8-sig")
                try:
                    ast.parse(source, filename=str(file))
                    checked += 1
                except SyntaxError as exc:
                    errors.append(f"Syntax error in {file}: {exc}")
            if actual.is_file():
                code = actual.read_text(encoding="utf-8-sig")
                if "_SCRIPTS_DIR = _Path(__file__).resolve().parents[1]" not in code:
                    errors.append(f"Script import bootstrap missing: {actual}")
                if "Path(__file__).resolve().parents[1]" in code.replace("_SCRIPTS_DIR = _Path(__file__).resolve().parents[1]", ""):
                    errors.append(f"Old project ROOT calculation may remain: {actual}")
    for category in MOVED:
        entry = SCRIPTS / category / "main.py"
        if not entry.is_file():
            errors.append(f"Missing launcher: {entry}")
    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(1)
    print(f"OK: {checked} Python files parsed, categorized implementations and wrappers are present.")
    print("Next: run dataset inventory and a small inference to verify runtime dependencies.")

if __name__ == "__main__":
    main()
