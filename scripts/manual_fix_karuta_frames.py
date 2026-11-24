"""Compatibility entry point; implementation moved to annotation/manual_fix_karuta_frames.py."""
from annotation.manual_fix_karuta_frames import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("annotation.manual_fix_karuta_frames", run_name="__main__", alter_sys=True)
