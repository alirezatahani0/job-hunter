from __future__ import annotations

import re
from typing import Any

import httpx

from job_assistant.services.eligibility import is_target_role
from job_assistant.state import Job

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class BoardBlocked(Exception):
    """The public page answered with a bot check instead of listings."""


def open_client() -> httpx.Client:
    return httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/json,application/rss+xml,*/*",
            "Accept-Language": "en",
        },
    )


def blocked_page(status: int, text: str) -> bool:
    if status in {401, 403, 429}:
        return True
    sample = text[:800].lower()
    return any(
        token in sample
        for token in ("just a moment", "security check", "cf-browser-verification", "attention required")
    )


def read_text(response: httpx.Response) -> str:
    content_type = (response.headers.get("content-type") or "").lower()
    if "1251" in content_type:
        return response.content.decode("windows-1251", errors="replace")
    return response.text


def fetch_text(url: str, *, client: httpx.Client, board: str) -> str:
    response = client.get(url)
    text = read_text(response)
    if blocked_page(response.status_code, text):
        raise BoardBlocked(f"{board} returned a bot check instead of listings.")
    response.raise_for_status()
    return text


def clean_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def make_job(
    *,
    source: str,
    job_id: str,
    title: str,
    company: str,
    location: str,
    url: str,
    description: str = "",
    tags: list[str] | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    salary_text: str | None = None,
) -> Job:
    title = re.sub(r"\s+", " ", title).strip()
    company = re.sub(r"\s+", " ", company).strip() or "Unknown"
    return Job(
        id=f"{source}-{job_id}",
        title=title,
        company=company,
        location=location.strip() or "Remote",
        tags=tags or [],
        salary_min=salary_min,
        salary_max=salary_max,
        salary_text=salary_text,
        url=url,
        description=(description or f"{title} at {company}. {location}.").strip()[:6000],
        category="software development",
        source=source,
    )


def keep_role(job: Job) -> bool:
    return bool(job.get("title")) and bool(job.get("url")) and is_target_role(job)


def dedupe(jobs: list[Job], limit: int) -> list[Job]:
    seen: set[str] = set()
    kept: list[Job] = []
    for job in jobs:
        if not keep_role(job):
            continue
        key = job["url"] or job["id"]
        if key in seen:
            continue
        seen.add(key)
        kept.append(job)
        if len(kept) >= limit:
            break
    return kept


def as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = re.search(r"\d[\d ]*", str(value))
    if not match:
        return None
    return int(match.group(0).replace(" ", ""))
