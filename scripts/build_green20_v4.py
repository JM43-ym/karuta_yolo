"""Compatibility entry point; implementation moved to dataset/build_green20_v4.py."""
from dataset.build_green20_v4 import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("dataset.build_green20_v4", run_name="__main__", alter_sys=True)
