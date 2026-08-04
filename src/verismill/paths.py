"""Platform paths for operator-owned verismill data."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def user_data_root() -> Path:
    """Return the per-user verismill data root without creating it."""
    configured = os.environ.get("VERISMILL_HOME")
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "verismill"
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA",
                                   Path.home() / "AppData" / "Local"))
        return base / "verismill"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "verismill"


def experiments_root() -> Path:
    """Return the default collection of user-owned experiments."""
    return user_data_root() / "experiments"
