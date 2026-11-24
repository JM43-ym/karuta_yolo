"""Compatibility entry point; implementation moved to annotation/annotate_green20_val_angles.py."""
from annotation.annotate_green20_val_angles import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("annotation.annotate_green20_val_angles", run_name="__main__", alter_sys=True)
