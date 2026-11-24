"""Compatibility entry point; implementation moved to dataset/build_green20_v3.py."""
from dataset.build_green20_v3 import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("dataset.build_green20_v3", run_name="__main__", alter_sys=True)
