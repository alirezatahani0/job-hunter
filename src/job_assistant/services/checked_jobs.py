"""Jobs already reviewed. A later fetch does not put them back on the board."""

from __future__ import annotations

import re
from pathlib import Path

CHECKED_JOBS_PATH = Path("data") / "checked_jobs.md"
_URL = re.compile(r"https?://\S+")


def clean_url(url: str) -> str:
    return (url or "").strip().rstrip(").,").rstrip("/")


def checked_urls_in(text: str) -> set[str]:
    found: set[str] = set()
    for line in (text or "").splitlines():
        if not line.strip().startswith("-"):
            continue
        match = _URL.search(line)
        if match:
            cleaned = clean_url(match.group(0))
            if cleaned:
                found.add(cleaned)
    return found


def load_checked_urls(path: Path | None = None) -> set[str]:
    file_path = path or CHECKED_JOBS_PATH
    if not file_path.exists():
        return set()
    return checked_urls_in(file_path.read_text(encoding="utf-8"))
