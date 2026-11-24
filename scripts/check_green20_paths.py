"""Compatibility entry point; implementation moved to dataset/check_green20_paths.py."""
from dataset.check_green20_paths import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("dataset.check_green20_paths", run_name="__main__", alter_sys=True)
