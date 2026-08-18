from __future__ import annotations

import re
from typing import Any

import httpx

from job_assistant.state import Job

REMOTEOK_API = "https://remoteok.com/api"
USER_AGENT = "job-assistant/0.1 (+https://github.com/example/job-assistant; contact=local)"


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _clean_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_job(raw: dict[str, Any]) -> Job | None:
    job_id = raw.get("id") or raw.get("slug")
    title = raw.get("position") or raw.get("title")
    if not job_id or not title:
        return None

    salary_min = _as_int(raw.get("salary_min"))
    salary_max = _as_int(raw.get("salary_max"))
    salary_text = None
    if salary_min or salary_max:
        lo = f"${salary_min:,}" if salary_min else "?"
        hi = f"${salary_max:,}" if salary_max else "?"
        salary_text = f"{lo} – {hi}"

    url = raw.get("url") or raw.get("apply_url") or ""
    if url and url.startswith("/"):
        url = f"https://remoteok.com{url}"

    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    description = raw.get("description") or ""
    if description:
        description = _clean_html(str(description))

    return Job(
        id=str(job_id),
        title=str(title),
        company=str(raw.get("company") or "Unknown"),
        location=str(raw.get("location") or "Remote"),
        tags=[str(t) for t in tags],
        salary_min=salary_min,
        salary_max=salary_max,
        salary_text=salary_text,
        url=str(url),
        description=description[:12000],
        source="remoteok",
    )


def fetch_remoteok_jobs(
    *,
    tags: list[str] | None = None,
    limit: int = 50,
    timeout: float = 30.0,
) -> list[Job]:
    """Fetch remote jobs from RemoteOK public API.

    First array element is legal metadata and is skipped.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        response = client.get(REMOTEOK_API)
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, list):
        raise ValueError("Unexpected RemoteOK response shape")

    jobs: list[Job] = []
    wanted = {t.lower() for t in (tags or []) if t}

    for item in payload:
        if not isinstance(item, dict) or "id" not in item:
            continue
        # Skip RemoteOK legal/meta rows and empty shells
        if item.get("legal") is not None and not item.get("position"):
            continue
        job = _normalize_job(item)
        if not job or not job["title"].strip():
            continue
        if wanted:
            haystack = " ".join(
                [
                    job["title"],
                    job["company"],
                    job["location"],
                    " ".join(job["tags"]),
                    job["description"][:2000],
                ]
            ).lower()
            if not any(tag in haystack for tag in wanted):
                continue
        jobs.append(job)

    return jobs[:limit]
