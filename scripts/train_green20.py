"""Backward-compatible facade for scripts/training/train_green20.py.

Imports re-export the implementation. CLI execution delegates directly to the
moved script without importing it twice.
"""
if __name__ == "__main__":
    from pathlib import Path
    import runpy
    runpy.run_path(str(Path(__file__).resolve().parent / "training/train_green20.py"), run_name="__main__")
else:
    from training.train_green20 import *
