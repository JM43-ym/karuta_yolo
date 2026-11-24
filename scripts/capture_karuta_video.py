"""Backward-compatible facade for scripts/gui/capture_karuta_video.py.

Imports re-export the implementation. CLI execution delegates directly to the
moved script without importing it twice.
"""
if __name__ == "__main__":
    from pathlib import Path
    import runpy
    runpy.run_path(str(Path(__file__).resolve().parent / "gui/capture_karuta_video.py"), run_name="__main__")
else:
    from gui.capture_karuta_video import *
