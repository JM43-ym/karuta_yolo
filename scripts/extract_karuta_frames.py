"""Compatibility entry point; implementation moved to capture/extract_karuta_frames.py."""
from capture.extract_karuta_frames import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("capture.extract_karuta_frames", run_name="__main__", alter_sys=True)
