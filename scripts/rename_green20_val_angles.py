"""Backward-compatible facade for scripts/renaming/rename_green20_val_angles.py.

Imports re-export the implementation. CLI execution delegates directly to the
moved script without importing it twice.
"""
if __name__ == "__main__":
    from pathlib import Path
    import runpy
    runpy.run_path(str(Path(__file__).resolve().parent / "renaming/rename_green20_val_angles.py"), run_name="__main__")
else:
    from renaming.rename_green20_val_angles import *
