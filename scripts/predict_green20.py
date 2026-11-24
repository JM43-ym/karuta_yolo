"""Compatibility entry point; implementation moved to inference/predict_green20.py."""
from inference.predict_green20 import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("inference.predict_green20", run_name="__main__", alter_sys=True)
