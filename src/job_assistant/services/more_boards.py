"""Extra remote boards: Jobicy, Daily Remote, JavaScript Jobs, Remote Frontend Jobs, React Jobs Board."""

from __future__ import annotations

import re
from html import unescape

from job_assistant.services.board_http import clean_html, dedupe, fetch_text, make_job, open_client
from job_assistant.state import Job

_FREE = {"anywhere", "worldwide", "global", "remote"}


def _place(value: str) -> str:
    text = re.sub(r"\s+", " ", unescape(value or "")).strip(" ·-")
    if not text or text.lower() in _FREE:
        return "Worldwide"
    return f"Remote, {text}"


def parse_jobicy(payload: dict) -> list[Job]:
    jobs: list[Job] = []
    for item in payload.get("jobs") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("jobTitle") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url:
            continue
        salary_min = item.get("salaryMin")
        salary_max = item.get("salaryMax")
        salary_text = None
        if isinstance(salary_min, int) or isinstance(salary_max, int):
            salary_text = f"{salary_min or '?'} – {salary_max or '?'} {item.get('salaryCurrency') or ''}".strip()
        jobs.append(
            make_job(
                source="jobicy",
                job_id=str(item.get("id") or url.rsplit("/", 1)[-1]),
                title=title,
                company=str(item.get("companyName") or "Unknown"),
                location=_place(str(item.get("jobGeo") or "")),
                url=url,
                description=clean_html(str(item.get("jobExcerpt") or item.get("jobDescription") or "")),
                salary_min=salary_min if isinstance(salary_min, int) else None,
                salary_max=salary_max if isinstance(salary_max, int) else None,
                salary_text=salary_text,
            )
        )
    return jobs


def parse_dailyremote(html: str) -> list[Job]:
    jobs: list[Job] = []
    for chunk in html.split("lst-card__title")[1:]:
        link = re.search(r'href="(/remote-job/([^"]+))"[^>]*>\s*([^<]+)', chunk)
        if not link:
            continue
        path, _slug, title = link.groups()
        place = ""
        for pill in re.findall(r'class="lst-pill"[^>]*>[\s\S]{0,300}?<span>([^<]+)</span>', chunk):
            label = pill.strip()
            low = label.lower()
            if not label or "yr" in low or "exp" in low or "full time" in low or "part time" in low:
                continue
            place = label
            break
        job_id = path.rstrip("/").rsplit("-", 1)[-1]
        jobs.append(
            make_job(
                source="dailyremote",
                job_id=job_id,
                title=unescape(title),
                company=f"Undisclosed {job_id}",
                location=_place(place),
                url=f"https://dailyremote.com{path}",
            )
        )
    return jobs


def parse_javascript_jobs(html: str) -> list[Job]:
    jobs: list[Job] = []
    for match in re.finditer(r'href="(https://javascript\.jobs/job/[^"]+)"', html):
        window = html[match.start() : match.start() + 2500]
        title = re.search(r'tw-text-lg tw-font-medium">\s*([^<]+)', window)
        company = re.search(r'tw-card-title">\s*([^<]+)', window)
        place = re.search(r'tw-location">\s*([^<]+)', window)
        if not title:
            continue
        url = match.group(1)
        jobs.append(
            make_job(
                source="javascriptjobs",
                job_id=url.rstrip("/").rsplit("/", 1)[-1],
                title=unescape(title.group(1)),
                company=unescape(company.group(1)).strip() if company else "Unknown",
                location=_place(place.group(1) if place else ""),
                url=url,
            )
        )
    return jobs


def parse_remote_frontend(html: str) -> list[Job]:
    jobs: list[Job] = []
    pattern = re.compile(
        r'href="(/[^"]+)"[\s\S]{0,900}?<h2[^>]*>\s*([^<]+)</h2>[\s\S]{0,500}?<p[^>]*>\s*([^<]+)<span[\s\S]{0,800}?</svg>\s*([^<]+)',
    )
    for path, title, company, place in pattern.findall(html):
        if path.startswith("/remote-"):
            continue
        url = path if path.startswith("http") else f"https://www.remotefrontendjobs.com{path}"
        jobs.append(
            make_job(
                source="remotefrontend",
                job_id=path.strip("/").split("-", 1)[0],
                title=unescape(title),
                company=unescape(company).strip(),
                location=_place(place),
                url=url,
            )
        )
    return jobs


def parse_reactjobsboard(html: str) -> list[Job]:
    jobs: list[Job] = []
    pattern = re.compile(
        r'href="(/remote-jobs/[^"]+)"[\s\S]{0,500}?<span>([^<]+)<span[^>]*>is hiring</span>'
        r'[\s\S]{0,300}?<span class="text-2xl[^"]*">([^<]+)</span>'
        r'[\s\S]{0,400}?Remote —</span><a[^>]*>([^<]+)</a>'
    )
    for path, company, title, place in pattern.findall(html):
        url = path if path.startswith("http") else f"https://reactjobsboard.com{path}"
        jobs.append(
            make_job(
                source="reactjobsboard",
                job_id=path.rstrip("/").split("/")[-1],
                title=unescape(title).strip(),
                company=unescape(company).strip(),
                location=_place(place),
                url=url,
            )
        )
    return jobs


def _collect(name: str, urls: list[str], parser, limit: int) -> list[Job]:
    jobs: list[Job] = []
    errors: list[Exception] = []
    with open_client() as client:
        for url in urls:
            try:
                jobs.extend(parser(fetch_text(url, client=client, board=name)))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
    if not jobs and errors:
        raise errors[0]
    return dedupe(jobs, limit)


def fetch_jobicy_jobs(*, limit: int = 40) -> list[Job]:
    jobs: list[Job] = []
    seen: set[str] = set()
    with open_client() as client:
        for tag in ("frontend", "react", "typescript", "fullstack", "nextjs"):
            response = client.get(
                "https://jobicy.com/api/v2/remote-jobs",
                params={"count": 50, "tag": tag},
            )
            response.raise_for_status()
            for job in parse_jobicy(response.json()):
                if job["url"] in seen:
                    continue
                seen.add(job["url"])
                jobs.append(job)
    return dedupe(jobs, limit)


def fetch_dailyremote_jobs(*, limit: int = 40) -> list[Job]:
    return _collect(
        "Daily Remote",
        [
            "https://dailyremote.com/remote-javascript-jobs",
            "https://dailyremote.com/remote-software-development-jobs",
        ],
        parse_dailyremote,
        limit,
    )


def fetch_javascript_jobs(*, limit: int = 40) -> list[Job]:
    return _collect(
        "JavaScript Jobs",
        ["https://javascript.jobs/remote"],
        parse_javascript_jobs,
        limit,
    )


def fetch_remote_frontend_jobs(*, limit: int = 40) -> list[Job]:
    return _collect(
        "Remote Frontend Jobs",
        [
            "https://www.remotefrontendjobs.com/remote-react-jobs",
            "https://www.remotefrontendjobs.com/remote-frontend-jobs",
            "https://www.remotefrontendjobs.com/remote-javascript-jobs",
        ],
        parse_remote_frontend,
        limit,
    )


def fetch_reactjobsboard_jobs(*, limit: int = 40) -> list[Job]:
    return _collect(
        "React Jobs Board",
        [
            "https://reactjobsboard.com/",
            "https://reactjobsboard.com/remote-react-jobs",
            "https://reactjobsboard.com/remote-typescript-jobs",
        ],
        parse_reactjobsboard,
        limit,
    )
