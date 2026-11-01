"""Launcher: this script lives in dot-map-convert/adapters/game-playground-maps/import_bsp.py, the family's one converter repository."""
import os
import sys

_C = os.environ.get("DOTBSP_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "dot-map-convert")
sys.path.insert(0, os.path.join(_C, "adapters"))
import adapter_launch  # noqa: E402
adapter_launch.run(globals(), "game-playground-maps", "import_bsp.py")
