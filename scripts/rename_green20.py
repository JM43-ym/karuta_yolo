"""Compatibility entry point; implementation moved to renaming/rename_green20.py."""
from renaming.rename_green20 import *
if __name__ == "__main__":
    import runpy
    runpy.run_module("renaming.rename_green20", run_name="__main__", alter_sys=True)
