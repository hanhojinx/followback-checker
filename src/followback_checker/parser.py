"""Parse Meta follower/following JSON or HTML, directories and ZIP archives."""

import json
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

from .comparator import Relationships, normalize_username

FILE_PATTERN = re.compile(r"^(followers|following)(?:_\d+)?\.(json|html)$", re.I)
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024


def username_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or parsed.hostname not in {
        "instagram.com", "www.instagram.com",
    }:
        return None
    parts = [unquote(x) for x in parsed.path.split("/") if x]
    if len(parts) == 2 and parts[0] == "_u":
        parts = parts[1:]
    if len(parts) != 1 or parts[0] in {"accounts", "explore", "p", "reel", "direct"}:
        return None
    return normalize_username(parts[0])


class ProfileLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.usernames: set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                username = username_from_url(href)
                if username:
                    self.usernames.add(username)


def parse_document(content: bytes, suffix: str, kind: str) -> set[str]:
    text = content.decode("utf-8-sig")
    if suffix.lower() == ".html":
        parser = ProfileLinks()
        parser.feed(text)
        if not parser.usernames:
            # A known empty export heading distinguishes an empty list from
            # unrelated HTML that would otherwise silently produce false results.
            heading = "followers" if kind == "followers" else "following"
            if not re.search(rf"\b{heading}\b", text, re.I):
                raise ValueError("HTML does not contain profile links or a relationship heading")
        return parser.usernames
    data = json.loads(text)
    if isinstance(data, dict):
        key = f"relationships_{kind}"
        if key not in data:
            raise ValueError(f"Expected JSON key {key!r}")
        data = data[key]
    if not isinstance(data, list):
        raise ValueError("Expected a relationship array")
    result = set()
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError("Relationship entries must be objects")
        values = entry.get("string_list_data", [])
        if not isinstance(values, list):
            raise ValueError("string_list_data must be an array")
        usernames = []
        for item in values:
            if not isinstance(item, dict):
                raise ValueError("string_list_data entries must be objects")
            value = item.get("value")
            if value:
                usernames.append(normalize_username(value))
            elif item.get("href"):
                name = username_from_url(item["href"])
                if name:
                    usernames.append(name)
        if not usernames and entry.get("title"):
            usernames.append(normalize_username(entry["title"]))
        if not usernames:
            raise ValueError("Relationship entry has no valid username")
        result.update(usernames)
    return result


def load_export(path: Path) -> Relationships:
    path = path.expanduser()
    found: dict[str, set[str]] = {}
    total = 0

    def consume(name: str, size: int, read):
        nonlocal total
        match = FILE_PATTERN.fullmatch(PurePosixPath(name.replace("\\", "/")).name)
        if not match:
            return
        total += size
        if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError("Export exceeds the parsing size limit (32 MiB/file, 128 MiB total)")
        kind = match[1].lower()
        try:
            users = parse_document(read(), "." + match[2], kind)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f"Cannot parse {name}: {exc}") from exc
        found.setdefault(kind, set()).update(users)

    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    consume(info.filename, info.file_size, lambda i=info: archive.read(i))
    elif path.is_dir() or path.is_file():
        if path.is_file() and not FILE_PATTERN.fullmatch(path.name):
            raise ValueError("Expected a ZIP or a followers/following JSON or HTML filename")
        # A single standard-named file means use its siblings too; both sets
        # are mandatory, including intentionally empty JSON arrays.
        root = path if path.is_dir() else path.parent
        files = root.rglob("*") if path.is_dir() else root.iterdir()
        for file in sorted(files):
            if file.is_file():
                consume(str(file), file.stat().st_size, file.read_bytes)
    else:
        raise ValueError(f"Export path does not exist: {path}")
    missing = {"followers", "following"} - found.keys()
    if missing:
        raise ValueError("Missing export files: " + ", ".join(sorted(missing)))
    return Relationships.from_iterables(found["followers"], found["following"])
