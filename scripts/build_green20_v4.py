"""Backward-compatible facade for scripts/dataset/build_green20_v4.py.

Imports re-export the implementation. CLI execution delegates directly to the
moved script without importing it twice.
"""
if __name__ == "__main__":
    from pathlib import Path
    import runpy
    runpy.run_path(str(Path(__file__).resolve().parent / "dataset/build_green20_v4.py"), run_name="__main__")
else:
    from dataset.build_green20_v4 import *
