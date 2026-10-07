"""Extension boundary for a future user-controlled browser session."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BrowserSessionReference:
    """Reference only. Never reads, copies, or persists session credentials."""

    profile_directory: Path
    browser: str = "chromium"
