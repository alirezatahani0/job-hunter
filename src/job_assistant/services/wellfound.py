from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx

from job_assistant.state import Job

BASE_URL = "https://wellfound.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Role slugs relevant to Alireza's profile
DEFAULT_ROLES = (
    "frontend-engineer",
    "full-stack-engineer",
    "software-engineer",
    "react-developer",
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
    "ui engineer",
    "web engineer",
)


def _parse_compensation(text: str | None) -> tuple[int | None, int | None, str | None]:
    if not text:
        return None, None, None
    clean = text.strip()
    # e.g. "$85k – $120k • No equity"
    nums = []
    for match in re.finditer(r"\$?\s*(\d+(?:\.\d+)?)\s*([kKmM])?", clean):
        value = float(match.group(1))
        suffix = (match.group(2) or "").lower()
        if suffix == "k":
            value *= 1_000
        elif suffix == "m":
            value *= 1_000_000
        nums.append(int(value))
        if len(nums) >= 2:
            break
    if not nums:
        return None, None, clean
    if len(nums) == 1:
        return nums[0], nums[0], clean
    return nums[0], nums[1], clean


def _extract_apollo_state(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        raise ValueError("Wellfound page missing __NEXT_DATA__ (possible bot challenge)")
    payload = json.loads(match.group(1))
    apollo = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("apolloState", {})
        .get("data")
    )
    if not isinstance(apollo, dict):
        raise ValueError("Wellfound Apollo state missing or unexpected shape")
    return apollo


def _startup_map(apollo: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for value in apollo.values():
        if isinstance(value, dict) and value.get("__typename") == "StartupResult":
            mapping[str(value.get("id"))] = value
            for ref in value.get("highlightedJobListings") or []:
                job_ref = ref.get("__ref") if isinstance(ref, dict) else None
                if job_ref:
                    mapping[f"job->{job_ref}"] = value
    return mapping


def _company_for_job(
    job_key: str, job: dict[str, Any], startups: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    direct = startups.get(f"job->JobListingSearchResult:{job.get('id')}")
    if direct:
        return direct
    direct = startups.get(f"job->{job_key}")
    if direct:
        return direct
    # Fallback: scan all startups for highlighted listing refs
    target = f"JobListingSearchResult:{job.get('id')}"
    for key, startup in startups.items():
        if key.startswith("job->"):
            continue
        for ref in startup.get("highlightedJobListings") or []:
            if isinstance(ref, dict) and ref.get("__ref") == target:
                return startup
    return None


def _location_text(job: dict[str, Any]) -> str:
    remote = bool(job.get("remote"))
    accepted = job.get("acceptedRemoteLocationNames") or []
    locations = job.get("locationNames") or []
    parts: list[str] = []
    if remote:
        parts.append("Remote")
    if accepted:
        parts.append("Accepted: " + ", ".join(str(x) for x in accepted[:8]))
    elif locations:
        parts.append(", ".join(str(x) for x in locations[:6]))
    return " | ".join(parts) if parts else "Remote"


def _is_relevant(job: dict[str, Any], *, prefer_remote: bool = True) -> bool:
    title = (job.get("title") or "").lower()
    role = (job.get("primaryRoleTitle") or "").lower()
    description = (job.get("description") or "").lower()
    blob = f"{title} {role} {description[:1200]}"
    if prefer_remote and not job.get("remote"):
        return False
    return any(hint in blob for hint in TITLE_HINTS)


def _to_job(job_key: str, raw: dict[str, Any], company: dict[str, Any] | None) -> Job:
    salary_min, salary_max, salary_text = _parse_compensation(raw.get("compensation"))
    company_name = (company or {}).get("name") or "Unknown"
    job_id = str(raw.get("id") or job_key)
    slug = raw.get("slug") or "job"
    url = f"{BASE_URL}/jobs/{job_id}-{slug}"

    tags: list[str] = []
    if raw.get("remote"):
        tags.append("remote")
    if raw.get("jobType"):
        tags.append(str(raw["jobType"]))
    if raw.get("primaryRoleTitle"):
        tags.append(str(raw["primaryRoleTitle"]))
    if company and company.get("companySize"):
        tags.append(str(company["companySize"]))
    # capture a couple of skill hints from description for ranking
    desc = (raw.get("description") or "").lower()
    for skill in ("react", "next.js", "typescript", "node.js", "graphql", "redux"):
        if skill in desc:
            tags.append(skill.replace(".", ""))

    return Job(
        id=f"wellfound-{job_id}",
        title=str(raw.get("title") or "Untitled"),
        company=str(company_name),
        location=_location_text(raw),
        tags=sorted(set(tags)),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_text=salary_text,
        url=url,
        description=str(raw.get("description") or ""),
        category=str(raw.get("primaryRoleTitle") or "Engineering"),
        source="wellfound",
    )


def _role_url(role: str, *, remote_only: bool, page: int) -> str:
    path = f"/role/r/{role}" if remote_only else f"/role/{role}"
    url = urljoin(BASE_URL, path)
    if page > 1:
        url = f"{url}?page={page}"
    return url


def fetch_wellfound_jobs(
    *,
    roles: list[str] | None = None,
    pages: int = 1,
    remote_only: bool = True,
    limit: int = 40,
    relevant_only: bool = True,
    timeout: float = 30.0,
) -> list[Job]:
    """Fetch relevant startup jobs from Wellfound role landing pages.

    Parses Apollo/`__NEXT_DATA__` embedded on pages such as:
    https://wellfound.com/role/r/frontend-engineer
    """
    roles = roles or list(DEFAULT_ROLES)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    by_id: dict[str, Job] = {}
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        for role in roles:
            for page in range(1, max(pages, 1) + 1):
                url = _role_url(role, remote_only=remote_only, page=page)
                response = client.get(url)
                response.raise_for_status()
                apollo = _extract_apollo_state(response.text)
                startups = _startup_map(apollo)

                for key, value in apollo.items():
                    if not (
                        isinstance(value, dict)
                        and value.get("__typename") == "JobListingSearchResult"
                    ):
                        continue
                    if relevant_only and not _is_relevant(
                        value, prefer_remote=remote_only
                    ):
                        continue
                    company = _company_for_job(key, value, startups)
                    job = _to_job(key, value, company)
                    by_id[job["id"]] = job
                    if len(by_id) >= limit:
                        return list(by_id.values())

    return list(by_id.values())
