"""Policy document version helpers.

Policy versions are labels, not decimal numbers.  The authoring stream starts
at v0.10 and increments the minor sequence as v0.11, v0.12, ... v0.20.

Legacy one-digit zero-series labels are parsed as their migrated sequence values
before sorting or incrementing.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Tuple


INITIAL_POLICY_VERSION = "v0.10"
POLICY_VERSION_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)(?P<suffix>_보완본)?$")


def parse_policy_version(version: str) -> Optional[Tuple[int, int, str]]:
    match = POLICY_VERSION_RE.fullmatch(str(version or "").strip())
    if not match:
        return None
    major = int(match.group("major"))
    minor_text = match.group("minor")
    minor = int(minor_text)
    if major == 0 and len(minor_text) == 1:
        minor += 9
    return major, minor, match.group("suffix") or ""


def format_policy_version(major: int, minor: int, suffix: str = "") -> str:
    return f"v{int(major)}.{int(minor):02d}{suffix or ''}"


def next_policy_version(versions: Iterable[str]) -> str:
    parsed = [item for item in (parse_policy_version(version) for version in versions) if item is not None]
    if not parsed:
        return INITIAL_POLICY_VERSION
    major, minor, _suffix = max(parsed, key=lambda item: (item[0], item[1], 1 if item[2] else 0))
    return format_policy_version(major, minor + 1)


def policy_version_sort_key(version: str) -> Tuple[int, int, int]:
    parsed = parse_policy_version(version)
    if parsed is None:
        return (0, 0, 0)
    major, minor, suffix = parsed
    return (major, minor, 1 if suffix else 0)
