"""Compatibility entry point; implementation moved to annotation/annotate_multi_val.py."""
from annotation.annotate_multi_val import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("annotation.annotate_multi_val", run_name="__main__", alter_sys=True)
