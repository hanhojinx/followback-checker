"""Replaceable data-source interface. No network requests in this release."""

from pathlib import Path
from typing import Protocol

from .comparator import Relationships
from .parser import load_export


class Fetcher(Protocol):
    def fetch(self) -> Relationships: ...


class ExportFetcher:
    def __init__(self, path: Path):
        self.path = path

    def fetch(self) -> Relationships:
        return load_export(self.path)


class LiveFetcher:
    def fetch(self) -> Relationships:
        raise NotImplementedError(
            "Live fetching is not implemented. Use --source export with a Meta "
            "export. A future adapter may use a browser session you control; "
            "automatic login and password storage are not supported."
        )
