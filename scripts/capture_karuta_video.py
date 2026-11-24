"""Compatibility entry point; implementation moved to gui/capture_karuta_video.py."""
from gui.capture_karuta_video import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("gui.capture_karuta_video", run_name="__main__", alter_sys=True)
