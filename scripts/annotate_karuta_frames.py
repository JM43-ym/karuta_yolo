"""Compatibility entry point; implementation moved to annotation/annotate_karuta_frames.py."""
from annotation.annotate_karuta_frames import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("annotation.annotate_karuta_frames", run_name="__main__", alter_sys=True)
