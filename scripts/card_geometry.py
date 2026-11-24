"""Compatibility entry point; implementation moved to inference/card_geometry.py."""
from inference.card_geometry import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("inference.card_geometry", run_name="__main__", alter_sys=True)
