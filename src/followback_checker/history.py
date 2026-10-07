"""Versioned snapshots with atomic saves and account-separated history."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .comparator import Relationships, changes


def atomic_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".fbchk-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_snapshot(directory: Path, account: str, relationships: Relationships) -> Path:
    now = datetime.now().astimezone()
    payload = {
        "schema_version": 1,
        "account": account,
        "created_at": now.isoformat(),
        "followers": sorted(relationships.followers),
        "following": sorted(relationships.following),
    }
    path = directory / (now.strftime("%Y-%m-%d_%H%M%S_%f") + "_" + uuid4().hex[:8] + ".json")
    atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def load_snapshots(directory: Path, account: str) -> list[tuple[Path, dict, Relationships]]:
    snapshots = []
    for path in directory.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload["schema_version"] != 1:
                raise ValueError("Unsupported snapshot schema")
            if payload["account"] != account:
                continue
            created = datetime.fromisoformat(payload["created_at"])
            if created.tzinfo is None:
                raise ValueError("Snapshot timestamp must include a timezone")
            if not all(isinstance(payload[key], list) for key in ("followers", "following")):
                raise ValueError("Snapshot relationships must be arrays")
            relationships = Relationships.from_iterables(payload["followers"], payload["following"])
            snapshots.append((path, payload, relationships))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"Invalid snapshot {path}: {exc}") from exc
    return sorted(snapshots, key=lambda item: (
        datetime.fromisoformat(item[1]["created_at"]), item[0].name,
    ))


def latest_changes(snapshots) -> dict[str, list[str]] | None:
    if len(snapshots) < 2:
        return None
    return changes(snapshots[-2][2], snapshots[-1][2])
