"""Compatibility entry point; implementation moved to dataset/generate_rotations.py."""
from dataset.generate_rotations import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("dataset.generate_rotations", run_name="__main__", alter_sys=True)
