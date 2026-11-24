"""Backward-compatible facade for scripts/inference/card_geometry.py.

Imports re-export the implementation. CLI execution delegates directly to the
moved script without importing it twice.
"""
if __name__ == "__main__":
    from pathlib import Path
    import runpy
    runpy.run_path(str(Path(__file__).resolve().parent / "inference/card_geometry.py"), run_name="__main__")
else:
    from inference.card_geometry import *
