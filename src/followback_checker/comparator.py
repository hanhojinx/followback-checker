"""Pure comparison functions, independent of input and storage."""

import re
from dataclasses import dataclass
from typing import Iterable

USERNAME = re.compile(r"[a-z0-9_.]{1,30}", re.ASCII)


def normalize_username(value: str) -> str:
    username = value.strip().removeprefix("@").lower()
    if not USERNAME.fullmatch(username):
        raise ValueError(f"Invalid Instagram username: {value!r}")
    return username


@dataclass(frozen=True)
class Relationships:
    followers: frozenset[str]
    following: frozenset[str]

    @classmethod
    def from_iterables(cls, followers: Iterable[str], following: Iterable[str]):
        return cls(
            frozenset(normalize_username(x) for x in followers),
            frozenset(normalize_username(x) for x in following),
        )

    @property
    def nonfollowers(self) -> list[str]:
        return sorted(self.following - self.followers)

    @property
    def mutual(self) -> frozenset[str]:
        return self.followers & self.following


def changes(previous: Relationships, current: Relationships) -> dict[str, list[str]]:
    return {
        "unfollowed_you": sorted(previous.followers - current.followers),
        "new_followers": sorted(current.followers - previous.followers),
        "you_followed": sorted(current.following - previous.following),
        "you_unfollowed": sorted(previous.following - current.following),
        "current_non_mutual": current.nonfollowers,
    }
