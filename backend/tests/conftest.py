"""Make `backend/` importable so tests can `import app...` and `import demo...`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
