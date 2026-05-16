# AI Quant Backend Package
import sys
from pathlib import Path

# Add backend directory to sys.path for absolute imports
_backend_dir = Path(__file__).parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from .app import app, create_app

__all__ = ["app", "create_app"]
