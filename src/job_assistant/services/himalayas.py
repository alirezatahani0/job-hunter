from __future__ import annotations

import re
from typing import Any

import httpx

from job_assistant.state import Job

BROWSE_API = "https://himalayas.app/jobs/api"
SEARCH_API = "https://himalayas.app/jobs/api/search"
USER_AGENT = "job-assistant/0.1 (+https://himalayas.app; educational use)"

# Himalayas encodes "all timezones" as this full UTC offset list (~37 values).
ALL_TZ_MIN_COUNT = 30

DEFAULT_QUERIES = (
    "frontend engineer",
    "full stack engineer",
    "react",
)


def _clean_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _location_names(raw: Any) -> list[str]:
    names: list[str] = []
    if not raw:
        return names
    if isinstance(raw, str):
        return [raw]
    if not isinstance(raw, list):
        return names
    for item in raw:
        if isinstance(item, str) and item.strip():
            names.append(item.strip())
        elif isinstance(item, dict):
            name = item.get("name") or item.get("slug") or item.get("alpha2")
            if name:
                names.append(str(name))
    return names


def _timezone_values(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw]
    values: list[str] = []
    for item in raw:
        if item is None or item == "":
            continue
        if isinstance(item, str) and item.upper().startswith("UTC"):
            values.append(item)
        else:
            try:
                number = float(item)
            except (TypeError, ValueError):
                values.append(str(item))
                continue
            sign = "+" if number >= 0 else ""
            if number == int(number):
                values.append(f"UTC{sign}{int(number)}")
            else:
                values.append(f"UTC{sign}{number}")
    return values


def is_worldwide_location(raw: Any) -> bool:
    """Empty locationRestrictions means Worldwide / all countries."""
    names = _location_names(raw)
    if not names:
        return True
    blob = " ".join(names).lower()
    return any(
        token in blob
        for token in ("worldwide", "anywhere", "all countries", "all country")
    )


def is_all_timezones(raw: Any) -> bool:
    """Empty or near-complete timezone list means Hiring timezones = all."""
    values = _timezone_values(raw)
    if not values:
        return True
    if len(values) >= ALL_TZ_MIN_COUNT:
        return True
    blob = " ".join(values).lower()
    return any(token in blob for token in ("worldwide", "all timezones", "any timezone"))


def _salary_text(
    min_salary: int | None,
    max_salary: int | None,
    currency: str | None,
    period: str | None,
) -> str | None:
    if min_salary is None and max_salary is None:
        return None
    cur = (currency or "USD").upper()
    period_label = ""
    if period and period.lower() not in {"annual", "yearly"}:
        period_label = f" / {period.lower()}"

    def fmt(value: int | None) -> str:
        if value is None:
            return "?"
        return f"{cur} {value:,}"

    if min_salary is not None and max_salary is not None:
        return f"{fmt(min_salary)} – {fmt(max_salary)}{period_label}"
    return f"{fmt(min_salary or max_salary)}{period_label}"


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_job(raw: dict[str, Any]) -> Job:
    locations = _location_names(raw.get("locationRestrictions"))
    timezones = _timezone_values(raw.get("timezoneRestrictions"))
    location_label = ", ".join(locations) if locations else "Worldwide / all countries"
    timezone_label = ", ".join(timezones) if timezones else "All timezones"
    if is_all_timezones(raw.get("timezoneRestrictions")):
        timezone_label = "All timezones"

    guid = str(raw.get("guid") or raw.get("applicationLink") or "")
    job_id = guid.rstrip("/").split("/")[-1] if guid else str(raw.get("title") or "job")

    tags = [str(t) for t in (raw.get("categories") or [])[:12]]
    tags.extend(str(t) for t in (raw.get("seniority") or []))
    if raw.get("employmentType"):
        tags.append(str(raw["employmentType"]))

    min_salary = _as_int(raw.get("minSalary"))
    max_salary = _as_int(raw.get("maxSalary"))
    description = _clean_html(str(raw.get("description") or raw.get("excerpt") or ""))

    return Job(
        id=f"himalayas-{job_id}",
        title=str(raw.get("title") or "Untitled"),
        company=str(raw.get("companyName") or "Unknown"),
        location=location_label,
        tags=sorted(set(tags)),
        salary_min=min_salary,
        salary_max=max_salary,
        salary_text=_salary_text(
            min_salary,
            max_salary,
            raw.get("currency"),
            raw.get("salaryPeriod"),
        ),
        url=guid or "https://himalayas.app/jobs",
        description=description[:12000],
        category=(raw.get("parentCategories") or ["Engineering"])[0],
        source="himalayas",
        hiring_timezones=timezone_label,
        location_requirements=location_label,
    )


def _is_relevant_title(job: Job, query: str | None = None) -> bool:
    blob = " ".join(
        [
            job.get("title") or "",
            " ".join(job.get("tags") or []),
            (job.get("description") or "")[:800],
        ]
    ).lower()
    hints = (
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
        "ui engineer",
    )
    if query:
        hints = (query.lower(), *hints)
    return any(hint in blob for hint in hints)


def fetch_himalayas_jobs(
    *,
    queries: list[str] | None = None,
    pages: int = 3,
    limit: int = 40,
    worldwide_only: bool = True,
    relevant_only: bool = True,
    timeout: float = 30.0,
) -> list[Job]:
    """Fetch Himalayas remote jobs.

    Keeps listings whose Location requirements are Worldwide / all countries
    and Hiring timezones are unrestricted / all timezones.
    """
    queries = [q.strip() for q in (queries or list(DEFAULT_QUERIES)) if q and q.strip()]
    if not queries:
        queries = list(DEFAULT_QUERIES)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    by_id: dict[str, Job] = {}

    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        for query in queries:
            for page in range(1, max(pages, 1) + 1):
                params: dict[str, Any] = {
                    "q": query,
                    "sort": "recent",
                    "page": page,
                }
                if worldwide_only:
                    params["worldwide"] = "true"
                response = client.get(SEARCH_API, params=params)
                response.raise_for_status()
                payload = response.json()
                jobs_raw = payload.get("jobs") if isinstance(payload, dict) else None
                if not isinstance(jobs_raw, list) or not jobs_raw:
                    break

                for raw in jobs_raw:
                    if not isinstance(raw, dict):
                        continue
                    if worldwide_only and not (
                        is_worldwide_location(raw.get("locationRestrictions"))
                        and is_all_timezones(raw.get("timezoneRestrictions"))
                    ):
                        continue
                    job = _to_job(raw)
                    if relevant_only and not _is_relevant_title(job, query):
                        continue
                    by_id[job["id"]] = job
                    if len(by_id) >= limit:
                        return list(by_id.values())

    return list(by_id.values())
