"""Backward-compatible facade for scripts/inference/prediction_history.py.

Imports re-export the implementation. CLI execution delegates directly to the
moved script without importing it twice.
"""
if __name__ == "__main__":
    from pathlib import Path
    import runpy
    runpy.run_path(str(Path(__file__).resolve().parent / "inference/prediction_history.py"), run_name="__main__")
else:
    from inference.prediction_history import *
