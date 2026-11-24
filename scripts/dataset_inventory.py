"""Compatibility entry point; implementation moved to dataset/dataset_inventory.py."""
from dataset.dataset_inventory import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("dataset.dataset_inventory", run_name="__main__", alter_sys=True)
