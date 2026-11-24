"""Compatibility entry point; implementation moved to annotation/auto_annotate.py."""
from annotation.auto_annotate import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("annotation.auto_annotate", run_name="__main__", alter_sys=True)
