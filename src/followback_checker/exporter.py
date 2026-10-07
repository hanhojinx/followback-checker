"""Deterministic CSV, TXT and JSON reports."""

import csv
import io
import json
from datetime import datetime
from pathlib import Path

from .history import atomic_text


def export_report(usernames: list[str], directory: Path, format: str) -> Path:
    if format not in {"csv", "txt", "json"}:
        raise ValueError(f"Unsupported output format: {format}")
    usernames = sorted(set(usernames))
    stem = "not_following_back_" + datetime.now().strftime("%Y-%m-%d")
    path = directory / f"{stem}.{format}"
    index = 1
    while path.exists():
        path = directory / f"{stem}_{index}.{format}"
        index += 1
    if format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["username", "profile_url"])
        writer.writerows((u, f"https://www.instagram.com/{u}/") for u in usernames)
        content = stream.getvalue()
    elif format == "txt":
        content = "".join(f"@{u}\n" for u in usernames)
    else:
        content = json.dumps({"not_following_back": usernames}, ensure_ascii=False, indent=2) + "\n"
    atomic_text(path, content)
    return path
