from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from job_assistant.services.board_http import (
    dedupe,
    fetch_text,
    make_job,
    open_client,
)
from job_assistant.state import Job

DEV_PAGES = (
    "https://dev.bg/company/jobs/front-end-development/remote/",
    "https://dev.bg/company/jobs/full-stack-development/remote/",
    "https://dev.bg/company/jobs/react/remote/",
    "https://dev.bg/company/jobs/javascript/remote/",
)

NOFLUFF_CATEGORIES = ("frontend", "fullstack", "javascript")


def parse_devbg(html: str, *, remote: bool = False) -> list[Job]:
    jobs: list[Job] = []
    for part in re.split(r'class="job-list-item', html)[1:]:
        url_match = re.search(r'href="(https://dev\.bg/company/jobads/[^"]+)"', part)
        title_match = re.search(r'class="job-title[^"]*"[^>]*>\s*([^<]+)', part)
        company_match = re.search(r'class="company-name[^"]*"[^>]*>\s*([^<]+)', part)
        if not url_match or not title_match:
            continue
        badges = [
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", badge)).strip()
            for badge in re.findall(r'class=" badge[^"]*"[^>]*>(.*?)</span>', part, re.S)
        ]
        places = [badge for badge in badges if badge]
        listed_remote = any(
            "remote" in place.lower() or "дистанц" in place.lower() for place in places
        )
        is_remote = remote or listed_remote
        location = ", ".join(places) or "Bulgaria"
        if is_remote and "remote" not in location.lower() and "дистанц" not in location.lower():
            location = f"Remote, {location}"
        if is_remote and not any(token in location.lower() for token in ("bulgaria", "sofia", "софия")):
            location = f"{location}, Bulgaria"
        job_id = re.search(r'data-job-id="(\d+)"', part)
        jobs.append(
            make_job(
                source="devbg",
                job_id=(job_id.group(1) if job_id else url_match.group(1).rstrip("/").split("/")[-1]),
                title=unescape(title_match.group(1)),
                company=unescape(company_match.group(1)) if company_match else "Unknown",
                location=location,
                url=url_match.group(1),
            )
        )
    return jobs


def parse_jobsbg(html: str) -> list[Job]:
    jobs: list[Job] = []
    for href, title in re.findall(
        r'href="(https://www\.jobs\.bg/(?:en/)?job/\d+[^"]*)"[^>]*>\s*([^<]{4,160})',
        html,
        re.I,
    ):
        jobs.append(
            make_job(
                source="jobsbg",
                job_id=href.rstrip("/").split("/")[-1],
                title=title,
                company="Jobs.bg",
                location="Remote, Bulgaria",
                url=href,
            )
        )
    return jobs


def parse_jobtiger(html: str) -> list[Job]:
    jobs: list[Job] = []
    chunks = re.split(r'(?=<a href="/obiavi-za-rabota/)', html)
    for part in chunks[1:]:
        href = re.search(r'href="(/obiavi-za-rabota/[^"]+)"', part)
        title = re.search(r'class="jt-card__title"[^>]*>\s*([^<]+)', part)
        company = re.search(r'class="jt-card__company"[^>]*>\s*([^<]+)', part)
        location = re.search(r'class="jt-card__location"[^>]*>(.*?)</div>', part, re.S)
        if not href or not title:
            continue
        place = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", location.group(1))).strip() if location else "Bulgaria"
        if "bulgaria" not in place.lower() and "sofia" not in place.lower():
            place = f"{place}, Bulgaria"
        slug = href.group(1).strip("/").split("/")[-1]
        jobs.append(
            make_job(
                source="jobtiger",
                job_id=slug,
                title=unescape(title.group(1)),
                company=company.group(1) if company else "Unknown",
                location=place,
                url=f"https://www.jobtiger.bg{href.group(1)}",
            )
        )
    return jobs


def parse_rabota(html: str) -> list[Job]:
    jobs: list[Job] = []
    for href, title in re.findall(
        r'href="(https://www\.rabota\.bg/[^"]*obiava[^"]+)"[^>]*>\s*([^<]{4,160})',
        html,
        re.I,
    ):
        jobs.append(
            make_job(
                source="rabota",
                job_id=href.rstrip("/").split("/")[-1],
                title=title,
                company="Rabota.bg",
                location="Remote, Bulgaria",
                url=href,
            )
        )
    return jobs


def _nofluff_location(posting: dict[str, Any]) -> str | None:
    places = (posting.get("location") or {}).get("places") or []
    cities = []
    countries = []
    remote = bool(posting.get("fullyRemote"))
    for place in places:
        if not isinstance(place, dict):
            continue
        city = str(place.get("city") or "")
        country = (place.get("country") or {}).get("name") if isinstance(place.get("country"), dict) else ""
        if city.lower() == "remote":
            remote = True
        elif city:
            cities.append(city)
        if country:
            countries.append(str(country))
    if not remote:
        return None
    country = countries[0] if countries else ""
    if country and country.lower() not in {"bulgaria", "europe"}:
        where = country
    else:
        where = "Europe" if not country else country
    city_text = ", ".join(cities[:2])
    tail = ", ".join(part for part in (city_text, where) if part)
    return f"Remote, {tail}" if tail else "Remote"


def parse_nofluff(payload: dict[str, Any]) -> list[Job]:
    jobs: list[Job] = []
    for posting in payload.get("postings") or []:
        if not isinstance(posting, dict):
            continue
        location = _nofluff_location(posting)
        if not location:
            continue
        salary = posting.get("salary") or {}
        salary_min = salary.get("from") if isinstance(salary.get("from"), int) else None
        salary_max = salary.get("to") if isinstance(salary.get("to"), int) else None
        currency = salary.get("currency") or ""
        period = salary.get("period") or ""
        salary_text = None
        if salary_min or salary_max:
            salary_text = f"{salary_min or ''}-{salary_max or ''} {currency} / {period}".strip()
        slug = str(posting.get("url") or posting.get("id") or "")
        jobs.append(
            make_job(
                source="nofluff",
                job_id=str(posting.get("id") or slug),
                title=str(posting.get("title") or ""),
                company=str(posting.get("name") or "Unknown"),
                location=location,
                url=f"https://nofluffjobs.com/job/{slug}",
                tags=[str(item) for item in (posting.get("seniority") or [])],
                salary_min=salary_min,
                salary_max=salary_max,
                salary_text=salary_text,
                description=f"{posting.get('title')} at {posting.get('name')}. {location}.",
            )
        )
    return jobs


def parse_justjoin(html: str, *, remote: bool = False) -> list[Job]:
    jobs: list[Job] = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        elements = []
        if isinstance(data, dict):
            main = data.get("mainEntity") or data
            if isinstance(main, dict):
                elements = main.get("itemListElement") or []
        for item in elements:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            title = str(item.get("name") or "")
            if not url or not title:
                continue
            if not remote and "remote" not in f"{url} {title}".lower():
                continue
            slug = url.rstrip("/").split("/")[-1]
            company = slug.split("-")[0].replace("_", " ").title() or "Just Join IT"
            jobs.append(
                make_job(
                    source="justjoin",
                    job_id=slug,
                    title=title,
                    company=company,
                    location="Remote, Europe",
                    url=url,
                )
            )
    return jobs


def parse_bulldog(html: str) -> list[Job]:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    listings = payload.get("props", {}).get("pageProps", {}).get("jobs") or []
    jobs: list[Job] = []
    for item in listings:
        if not isinstance(item, dict) or not item.get("remote"):
            continue
        company = item.get("company") or {}
        company_name = company.get("name") if isinstance(company, dict) else "Unknown"
        job_id = str(item.get("id") or "")
        tags = [str(tag) for tag in (item.get("technologyTags") or [])]
        jobs.append(
            make_job(
                source="bulldog",
                job_id=job_id,
                title=str(item.get("position") or ""),
                company=str(company_name or "Unknown"),
                location="Remote, Europe",
                url=f"https://bulldogjob.com/companies/jobs/{job_id}",
                tags=tags,
                description=f"{item.get('position')} at {company_name}. Remote. {', '.join(tags)}.",
            )
        )
    return jobs


def _walk_jobs(node: Any, found: list[dict]) -> None:
    if isinstance(node, dict):
        kind = node.get("@type")
        if kind == "JobPosting" or kind == ["JobPosting"]:
            found.append(node)
        for value in node.values():
            _walk_jobs(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk_jobs(value, found)


def parse_djinni(html: str) -> list[Job]:
    found: list[dict] = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            _walk_jobs(json.loads(block), found)
        except json.JSONDecodeError:
            continue
    jobs: list[Job] = []
    for item in found:
        place = item.get("applicantLocationRequirements") or {}
        address = place.get("address") if isinstance(place, dict) else {}
        region = ""
        if isinstance(address, dict):
            region = str(address.get("addressRegion") or address.get("addressCountry") or "")
        location_type = str(item.get("jobLocationType") or "")
        if location_type and location_type.upper() != "TELECOMMUTE" and "remote" not in location_type.lower():
            continue
        org = item.get("hiringOrganization") or {}
        company = org.get("name") if isinstance(org, dict) else "Unknown"
        url = str(item.get("url") or "")
        where = region or "Europe"
        jobs.append(
            make_job(
                source="djinni",
                job_id=url.rstrip("/").split("/")[-1] or str(item.get("identifier") or item.get("title")),
                title=str(item.get("title") or ""),
                company=str(company or "Unknown"),
                location=f"Remote, {where}",
                url=url,
                description=str(item.get("description") or "")[:4000],
            )
        )
    return jobs


def fetch_devbg_jobs(*, limit: int = 40) -> list[Job]:
    jobs: list[Job] = []
    with open_client() as client:
        for url in DEV_PAGES:
            text = fetch_text(url, client=client, board="DEV.bg")
            jobs.extend(parse_devbg(text, remote=True))
    return dedupe(jobs, limit)


def fetch_jobsbg_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text(
            "https://www.jobs.bg/en/front_job_search.php?keyword=frontend",
            client=client,
            board="Jobs.bg",
        )
    return dedupe(parse_jobsbg(text), limit)


def fetch_jobtiger_jobs(*, limit: int = 40) -> list[Job]:
    jobs: list[Job] = []
    with open_client() as client:
        for keyword in ("frontend", "full stack", "react"):
            text = fetch_text(
                f"https://www.jobtiger.bg/obiavi-za-rabota/?keyword={keyword.replace(' ', '+')}&ln=1",
                client=client,
                board="JobTiger",
            )
            jobs.extend(parse_jobtiger(text))
    return dedupe(jobs, limit)


def fetch_rabota_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text(
            "https://www.rabota.bg/search.php?kw=frontend+developer",
            client=client,
            board="Rabota.bg",
        )
    return dedupe(parse_rabota(text), limit)


def fetch_nofluff_jobs(*, limit: int = 40) -> list[Job]:
    jobs: list[Job] = []
    with open_client() as client:
        for category in NOFLUFF_CATEGORIES:
            response = client.post(
                "https://nofluffjobs.com/api/search/posting",
                params={"salaryCurrency": "EUR", "salaryPeriod": "month"},
                json={"criteriaSearch": {"category": [category]}},
            )
            if response.status_code == 400:
                continue
            response.raise_for_status()
            jobs.extend(parse_nofluff(response.json()))
    return dedupe(jobs, limit)


def fetch_justjoin_jobs(*, limit: int = 40) -> list[Job]:
    jobs: list[Job] = []
    with open_client() as client:
        for keyword in ("frontend", "fullstack", "react"):
            text = fetch_text(
                f"https://justjoin.it/job-offers/remote?keyword={keyword}",
                client=client,
                board="Just Join IT",
            )
            jobs.extend(parse_justjoin(text, remote=True))
    return dedupe(jobs, limit)


def fetch_bulldog_jobs(*, limit: int = 40) -> list[Job]:
    jobs: list[Job] = []
    with open_client() as client:
        for role in ("frontend", "fullstack"):
            text = fetch_text(
                f"https://bulldogjob.com/companies/jobs/s/role,{role}",
                client=client,
                board="Bulldogjob",
            )
            jobs.extend(parse_bulldog(text))
    return dedupe(jobs, limit)


def fetch_djinni_jobs(*, limit: int = 40) -> list[Job]:
    jobs: list[Job] = []
    with open_client() as client:
        for keyword in ("Frontend", "Full-Stack", "React"):
            text = fetch_text(
                f"https://djinni.co/jobs/?primary_keyword={keyword}&remote_type=full_remote",
                client=client,
                board="Djinni",
            )
            jobs.extend(parse_djinni(text))
    return dedupe(jobs, limit)
