from pathlib import Path

_SRC_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "src" / "borehole_stick_gui"
__path__ = [str(_SRC_PACKAGE_DIR)]
