from __future__ import annotations

import sys
from pathlib import Path


def asset_root() -> Path:
    installed = Path(sys.prefix) / "share" / "e2e-verification"
    if installed.is_dir():
        return installed
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "schemas").is_dir() and (checkout / "skills").is_dir():
        return checkout
    raise FileNotFoundError("e2e-verification shared assets are not installed")

