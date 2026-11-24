"""Compatibility entry point; implementation moved to inference/prediction_history.py."""
from inference.prediction_history import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("inference.prediction_history", run_name="__main__", alter_sys=True)
