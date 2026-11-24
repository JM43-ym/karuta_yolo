"""Check categorized modules after removing legacy scripts/*.py shims.

Read-only: parses source, validates imports and entrypoints; no camera/GPU loads.
"""
from __future__ import annotations

import ast
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
GROUPS = {
    "annotation": ("auto_annotate", "annotate_karuta_frames",
        "annotate_green20_val_angles", "annotate_multi_val",
        "manual_fix_karuta_frames", "review_karuta_annotations"),
    "renaming": ("rename_green20", "rename_green20_val_angles"),
    "capture": ("extract_karuta_frames",),
    "gui": ("capture_karuta_video",),
    "dataset": ("generate_rotations", "build_green20_v3", "build_green20_v4",
        "build_green20_video_augmented", "dataset_inventory", "check_green20_paths"),
    "training": ("train_green20",),
    "inference": ("predict_green20", "card_geometry",
        "prediction_filter", "prediction_history"),
}
LEGACY = {name for names in GROUPS.values() for name in names}
ALLOW_ROOT = {"toolbox.py", "verify_script_layout.py"}

def main() -> None:
    errors: list[str] = []
    files = sorted(SCRIPTS.rglob("*.py"))
    count = 0
    for path in files:
        try:
            code = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(code, filename=str(path))
            count += 1
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(f"Cannot parse {path.relative_to(SCRIPTS)}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                if node.module and node.module.split(".", 1)[0] in LEGACY:
                    errors.append(f"Old unqualified import in {path.relative_to(SCRIPTS)}:{node.lineno}: {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in LEGACY:
                        errors.append(f"Old unqualified import in {path.relative_to(SCRIPTS)}:{node.lineno}: {alias.name}")
    roots = {p.name for p in SCRIPTS.glob("*.py")}
    missing = ALLOW_ROOT - roots
    unexpected = roots - ALLOW_ROOT
    if missing:
        errors.append(f"Missing shared scripts: {sorted(missing)}")
    if unexpected:
        errors.append(f"Unexpected top-level Python files: {sorted(unexpected)}")
    for category, names in GROUPS.items():
        folder = SCRIPTS / category
        for required in (folder / "__init__.py", folder / "main.py"):
            if not required.is_file():
                errors.append(f"Missing package/entry: {required.relative_to(SCRIPTS)}")
        for name in names:
            p = folder / f"{name}.py"
            if not p.is_file():
                errors.append(f"Missing implementation: {p.relative_to(SCRIPTS)}")
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import importlib.util
    for category, names in GROUPS.items():
        for name in names:
            module = f"{category}.{name}"
            try:
                if importlib.util.find_spec(module) is None:
                    errors.append(f"Cannot find package module: {module}")
            except (ImportError, ModuleNotFoundError) as exc:
                errors.append(f"Module spec error {module}: {exc}")
    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(1)
    print(f"OK: {count} Python files parsed; {len(LEGACY)} legacy wrappers are absent.")
    print("All categorized implementations, entrypoints and import specs were found.")
    print("Next: run --help on inference, training, annotation and capture GUI.")

if __name__ == "__main__":
    main()
