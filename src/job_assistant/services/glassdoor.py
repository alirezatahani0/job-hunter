from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx

from job_assistant.state import Job

BASE_URL = "https://www.glassdoor.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

DEFAULT_QUERIES = (
    "frontend engineer",
    "full stack engineer",
    "react",
)

TITLE_HINTS = (
    "frontend",
    "front-end",
    "front end",
    "full-stack",
    "fullstack",
    "full stack",
    "react",
    "next.js",
    "nextjs",
    "typescript",
    "javascript",
    "software engineer",
    "web engineer",
)


class GlassdoorBlocked(RuntimeError):
    """Glassdoor returned a bot challenge instead of job listings."""


def _clean_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_challenge(status: int, text: str) -> bool:
    lowered = text[:4000].lower()
    return status in {401, 403, 429} or any(
        token in lowered
        for token in (
            "just a moment",
            "security | glassdoor",
            "cf-browser-verification",
            "enable javascript and cookies",
        )
    )


def _search_url(query: str) -> str:
    from urllib.parse import urlencode

    return f"{BASE_URL}/Job/jobs.htm?{urlencode({'sc.keyword': query, 'fromAge': 1, 'remoteWorkType': 1})}"


def _job_from_posting(raw: dict[str, Any]) -> Job | None:
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    org = raw.get("hiringOrganization") or {}
    company = "Unknown"
    if isinstance(org, dict):
        company = str(org.get("name") or company)
    url = str(raw.get("url") or "")
    if url.startswith("/"):
        url = urljoin(BASE_URL, url)
    location = "Remote"
    place = raw.get("jobLocation")
    if isinstance(place, dict):
        address = place.get("address") or {}
        if isinstance(address, dict):
            locality = address.get("addressLocality") or address.get("addressCountry")
            if locality:
                location = f"Remote | {locality}"
    description = _clean_html(str(raw.get("description") or ""))
    job_id = str(raw.get("identifier") or url or title)
    if isinstance(raw.get("identifier"), dict):
        job_id = str(raw["identifier"].get("value") or job_id)
    return Job(
        id=f"glassdoor-{job_id}",
        title=title,
        company=company,
        location=location,
        tags=["remote", "glassdoor"],
        salary_min=None,
        salary_max=None,
        salary_text=None,
        url=url or BASE_URL,
        description=description[:12000],
        category="Engineering",
        source="glassdoor",
    )


def _postings_from_html(html: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for match in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "JobPosting":
                found.append(item)
            graph = item.get("@graph")
            if isinstance(graph, list):
                found.extend(
                    node
                    for node in graph
                    if isinstance(node, dict) and node.get("@type") == "JobPosting"
                )
    return found


def _is_relevant(job: Job) -> bool:
    blob = f"{job.get('title') or ''} {(job.get('description') or '')[:800]}".lower()
    return any(hint in blob for hint in TITLE_HINTS)


def fetch_glassdoor_jobs(
    *,
    queries: list[str] | None = None,
    limit: int = 40,
    relevant_only: bool = True,
    timeout: float = 30.0,
) -> list[Job]:
    """Fetch remote Glassdoor listings posted in the last day.

    Glassdoor has no public jobs API. This reads the same search pages a
    signed-out visitor gets. A Cloudflare challenge raises GlassdoorBlocked.
    """
    queries = [q.strip() for q in (queries or list(DEFAULT_QUERIES)) if q and q.strip()]
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    by_id: dict[str, Job] = {}
    blocked = 0
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        for query in queries:
            response = client.get(_search_url(query))
            if _is_challenge(response.status_code, response.text):
                blocked += 1
                continue
            response.raise_for_status()
            for raw in _postings_from_html(response.text):
                job = _job_from_posting(raw)
                if not job:
                    continue
                if relevant_only and not _is_relevant(job):
                    continue
                by_id[job["id"]] = job
                if len(by_id) >= limit:
                    return list(by_id.values())
    if not by_id and blocked:
        raise GlassdoorBlocked(
            "Glassdoor blocked the fetch with a bot check. Open the search in a browser to apply from there."
        )
    return list(by_id.values())
