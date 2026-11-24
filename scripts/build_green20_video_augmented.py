"""Compatibility entry point; implementation moved to dataset/build_green20_video_augmented.py."""
from dataset.build_green20_video_augmented import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("dataset.build_green20_video_augmented", run_name="__main__", alter_sys=True)
