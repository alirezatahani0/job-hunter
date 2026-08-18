from __future__ import annotations

import re
from typing import Any

import httpx

from job_assistant.state import Job

REMOTIVE_API = "https://remotive.com/api/remote-jobs"
USER_AGENT = "job-assistant/0.1 (+local; educational use)"


def _clean_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_salary(salary: str | None) -> tuple[int | None, int | None, str | None]:
    if not salary:
        return None, None, None
    text = salary.strip()
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text)]
    if not nums:
        return None, None, text
    if len(nums) == 1:
        return nums[0], nums[0], text
    return nums[0], nums[1], text


def _normalize_job(raw: dict[str, Any]) -> Job | None:
    job_id = raw.get("id")
    title = raw.get("title")
    if not job_id or not title:
        return None
    salary_min, salary_max, salary_text = _parse_salary(raw.get("salary"))
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    description = _clean_html(str(raw.get("description") or ""))
    return Job(
        id=f"remotive-{job_id}",
        title=str(title),
        company=str(raw.get("company_name") or "Unknown"),
        location=str(raw.get("candidate_required_location") or "Remote"),
        tags=[str(t) for t in tags],
        salary_min=salary_min,
        salary_max=salary_max,
        salary_text=salary_text,
        url=str(raw.get("url") or ""),
        description=description[:12000],
        category=str(raw.get("category") or ""),
        source="remotive",
    )


def fetch_remotive_jobs(
    *,
    search: str | None = None,
    category: str | None = None,
    limit: int = 50,
    timeout: float = 30.0,
) -> list[Job]:
    """Fetch remote jobs from Remotive public API."""
    params: dict[str, Any] = {"limit": max(limit, 20)}
    if search:
        params["search"] = search
    if category:
        params["category"] = category

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        response = client.get(REMOTIVE_API, params=params)
        response.raise_for_status()
        payload = response.json()

    jobs_raw = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs_raw, list):
        raise ValueError("Unexpected Remotive response shape")

    jobs: list[Job] = []
    for item in jobs_raw:
        if not isinstance(item, dict):
            continue
        job = _normalize_job(item)
        if job:
            jobs.append(job)
        if len(jobs) >= limit:
            break
    return jobs
