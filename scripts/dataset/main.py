"""dataset tools: categorized entry point, keeping existing script paths compatible."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from toolbox import main
if __name__ == "__main__":
    main("dataset")
