# tests/conftest.py
import sys
from pathlib import Path

# Miroir de App.py : on insère src/ sur le sys.path pour importer
# components/ et utils/ comme des packages de premier niveau.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
