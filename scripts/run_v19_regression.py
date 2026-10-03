"""Explicit v19 freeze/preflight; --live still requires a NEW version-bound approval."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.run_v18_regression import main

if __name__=='__main__':
    main('v19')
