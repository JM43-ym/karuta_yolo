"""Compatibility entry point; implementation moved to annotation/review_karuta_annotations.py."""
from annotation.review_karuta_annotations import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("annotation.review_karuta_annotations", run_name="__main__", alter_sys=True)
