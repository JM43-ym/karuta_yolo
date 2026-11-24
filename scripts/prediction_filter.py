"""Compatibility entry point; implementation moved to inference/prediction_filter.py."""
from inference.prediction_filter import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("inference.prediction_filter", run_name="__main__", alter_sys=True)
