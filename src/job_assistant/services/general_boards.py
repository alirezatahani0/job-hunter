from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from job_assistant.services.board_http import (
    clean_html,
    dedupe,
    fetch_text,
    make_job,
    open_client,
)
from job_assistant.state import Job


def parse_linkedin(html: str) -> list[Job]:
    jobs: list[Job] = []
    for part in re.split(r'data-entity-urn="urn:li:jobPosting:', html)[1:]:
        job_id = part.split('"', 1)[0]
        title = re.search(r'class="base-search-card__title"[^>]*>\s*([^<]+)', part)
        company = re.search(r'class="hidden-nested-link"[^>]*>\s*([^<]+)', part)
        location = re.search(r'class="job-search-card__location"[^>]*>\s*([^<]+)', part)
        href = re.search(r'href="(https://[^"]*linkedin\.com/jobs/view/[^"]+)"', part)
        if not title:
            continue
        place = location.group(1).strip() if location else ""
        where = f"Remote, {place}" if place else "Remote"
        url = href.group(1).split("?")[0] if href else f"https://www.linkedin.com/jobs/view/{job_id}"
        jobs.append(
            make_job(
                source="linkedin",
                job_id=job_id,
                title=unescape(title.group(1)),
                company=unescape(company.group(1)) if company else "Unknown",
                location=where,
                url=url,
            )
        )
    return jobs


def parse_indeed(xml_text: str) -> list[Job]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_text)
    jobs: list[Job] = []
    for item in root.iter("item"):
        title = unescape((item.findtext("title") or "")).strip()
        link = (item.findtext("link") or "").strip()
        location = ""
        for child in item:
            if child.tag.endswith("location") or child.tag == "location":
                location = unescape(child.text or "")
        where = location if "remote" in location.lower() else f"Remote, {location or 'Europe'}"
        jobs.append(
            make_job(
                source="indeed",
                job_id=link.rstrip("/").split("/")[-1] or title,
                title=title,
                company="Indeed",
                location=where,
                url=link,
                description=clean_html(unescape(item.findtext("description") or "")),
            )
        )
    return jobs


def parse_welcome(html: str) -> list[Job]:
    jobs: list[Job] = []
    for company, slug, title in re.findall(
        r'href="(?:https://www\.welcometothejungle\.com)?/en/companies/([^"/]+)/jobs/([^"/]+)"[^>]*>\s*([^<]{4,160})',
        html,
    ):
        jobs.append(
            make_job(
                source="welcometothejungle",
                job_id=slug,
                title=unescape(title),
                company=company.replace("-", " ").title(),
                location="Remote, Europe",
                url=f"https://www.welcometothejungle.com/en/companies/{company}/jobs/{slug}",
            )
        )
    return jobs


def _arc_location(countries: list) -> str | None:
    names = [str(country) for country in countries if country]
    if not names:
        return "Remote"
    lowered = {name.lower() for name in names}
    if lowered <= {"us", "usa", "united states"}:
        return "Remote, United States"
    if any(token in " ".join(lowered) for token in ("europe", "bulgaria", "worldwide", "anywhere")):
        return "Remote, Europe"
    if len(names) == 1:
        return f"Remote, {names[0]}"
    return "Remote, " + ", ".join(names[:4])


def parse_arc(page_props: dict[str, Any]) -> list[Job]:
    jobs: list[Job] = []
    for key in ("arcJobs", "externalJobs"):
        for item in page_props.get(key) or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("positionType") or item.get("jobRole") or "").lower() == "design":
                continue
            company = item.get("company") or {}
            company_name = company.get("name") if isinstance(company, dict) else ""
            slug = str(item.get("urlString") or item.get("randomKey") or "")
            if not company_name:
                company_name = f"Arc.dev ({slug.replace('-', ' ')[:42]})"
            location = _arc_location(list(item.get("requiredCountries") or []))
            if not location:
                continue
            tags = [
                str(category.get("name"))
                for category in (item.get("categories") or [])
                if isinstance(category, dict) and category.get("name")
            ]
            jobs.append(
                make_job(
                    source="arc",
                    job_id=str(item.get("randomKey") or slug),
                    title=str(item.get("title") or ""),
                    company=str(company_name or "Arc.dev"),
                    location=location,
                    url=f"https://arc.dev/remote-jobs/{slug}",
                    tags=tags,
                    salary_min=item.get("minAnnualSalary") if isinstance(item.get("minAnnualSalary"), int) else None,
                    salary_max=item.get("maxAnnualSalary") if isinstance(item.get("maxAnnualSalary"), int) else None,
                )
            )
    return jobs


def parse_arc_html(html: str) -> list[Job]:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        return []
    payload = json.loads(match.group(1))
    return parse_arc(payload.get("props", {}).get("pageProps") or {})


def parse_ycombinator(html: str) -> list[Job]:
    match = re.search(r'data-page="([^"]+)"', html)
    if not match:
        return []
    page = json.loads(unescape(match.group(1)))
    listings = (page.get("props") or {}).get("jobs") or []
    jobs: list[Job] = []
    for item in listings:
        if not isinstance(item, dict):
            continue
        location = str(item.get("location") or "")
        if "remote" not in location.lower() and "remote" not in str(item.get("title") or "").lower():
            continue
        where = location if "remote" in location.lower() else f"Remote, {location}"
        if re.search(r"\b(US|USA)\b", where) and "united states" not in where.lower():
            where = f"{where}, United States"
        job_id = str(item.get("id") or "")
        jobs.append(
            make_job(
                source="ycombinator",
                job_id=job_id,
                title=str(item.get("title") or ""),
                company=str(item.get("companyName") or "Unknown"),
                location=where,
                url=f"https://www.workatastartup.com/jobs/{job_id}",
                salary_text=str(item.get("salary") or "") or None,
                description=str(item.get("companyOneLiner") or ""),
            )
        )
    return jobs


def parse_hn(comments: list[dict]) -> list[Job]:
    jobs: list[Job] = []
    for comment in comments:
        text = clean_html(str(comment.get("comment_text") or ""))
        if "remote" not in text.lower():
            continue
        lines = [line.strip(" -*") for line in text.splitlines() if line.strip()]
        if not lines:
            continue
        head = lines[0].split("|")[0].strip()
        role_words = ("engineer", "developer", "frontend", "fullstack", "full-stack", "full stack")
        if any(word in head.lower() for word in role_words):
            company = f"HN {comment.get('objectID') or ''}".strip()
        else:
            company = head[:80] or "Hacker News"
        title = ""
        for line in lines:
            if any(token in line.lower() for token in ("frontend", "front-end", "full-stack", "fullstack", "full stack", "react")):
                title = line[:140]
                break
        if not title:
            continue
        object_id = str(comment.get("objectID") or "")
        jobs.append(
            make_job(
                source="hn",
                job_id=object_id,
                title=title,
                company=company,
                location="Remote",
                url=f"https://news.ycombinator.com/item?id={object_id}",
                description=text[:4000],
            )
        )
    return jobs


def parse_landing(html: str) -> list[Job]:
    jobs: list[Job] = []
    for href, title in re.findall(
        r'href="(https://landing\.jobs/(?:at/)?jobs/[^"]+)"[^>]*>\s*([^<]{4,160})',
        html,
    ):
        if "/for/" in href or href.rstrip("/").endswith("/jobs"):
            continue
        jobs.append(
            make_job(
                source="landing",
                job_id=href.rstrip("/").split("/")[-1],
                title=unescape(title),
                company="Landing.jobs",
                location="Remote, Europe",
                url=href,
            )
        )
    return jobs


def parse_relocate(html: str) -> list[Job]:
    jobs: list[Job] = []
    parts = re.split(r'class="job__info"', html)
    for part in parts[1:]:
        title_match = re.search(r'class="job__title"[^>]*>\s*<a href="([^"]+)"[^>]*>\s*<b>(.*?)</b>', part, re.S)
        company_match = re.search(r'class="job__company[^"]*"[^>]*>(.*?)</div>', part, re.S)
        if not title_match:
            continue
        href, title = title_match.group(1), re.sub(r"\s+", " ", title_match.group(2)).strip()
        company = clean_html(company_match.group(1)) if company_match else "Unknown"
        path = href if href.startswith("/") else "/" + href
        if path.startswith("/remote/") or "remote" in title.lower():
            location = "Remote"
        else:
            bits = [bit for bit in path.split("/") if bit and bit != "remote"]
            location = ", ".join(bits[:2]).replace("-", " ").title() or "On-site"
        url = href if href.startswith("http") else f"https://relocate.me{path}"
        jobs.append(
            make_job(
                source="relocate",
                job_id=path.rstrip("/").split("/")[-1],
                title=unescape(title),
                company=company or "Unknown",
                location=location,
                url=url,
            )
        )
    return jobs


def fetch_linkedin_jobs(*, limit: int = 40) -> list[Job]:
    jobs: list[Job] = []
    queries = ("frontend engineer", "full stack engineer", "react")
    with open_client() as client:
        for query in queries:
            for start in (0, 25):
                text = fetch_text(
                    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                    f"?keywords={query.replace(' ', '%20')}&f_WT=2&location=European%20Union&start={start}",
                    client=client,
                    board="LinkedIn",
                )
                jobs.extend(parse_linkedin(text))
    return dedupe(jobs, limit)


def fetch_indeed_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text(
            "https://www.indeed.com/rss?q=frontend+engineer&l=Remote",
            client=client,
            board="Indeed",
        )
    return dedupe(parse_indeed(text), limit)


def fetch_welcome_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text(
            "https://www.welcometothejungle.com/en/jobs?query=frontend%20engineer&aroundQuery=Europe",
            client=client,
            board="Welcome to the Jungle",
        )
    jobs = dedupe(parse_welcome(text), limit)
    if not jobs:
        raise ValueError("Welcome to the Jungle did not include job listings on the public page.")
    return jobs


def fetch_arc_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text("https://arc.dev/remote-jobs", client=client, board="Arc")
    return dedupe(parse_arc_html(text), limit)


def fetch_ycombinator_jobs(*, limit: int = 40) -> list[Job]:
    jobs: list[Job] = []
    with open_client() as client:
        for url in (
            "https://www.workatastartup.com/jobs",
            "https://www.workatastartup.com/",
        ):
            text = fetch_text(url, client=client, board="Y Combinator")
            jobs.extend(parse_ycombinator(text))
    return dedupe(jobs, limit)


def fetch_hn_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        search = client.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": "Ask HN: Who is hiring?", "tags": "story", "hitsPerPage": 1},
        )
        search.raise_for_status()
        hits = search.json().get("hits") or []
        if not hits:
            return []
        story_id = hits[0].get("objectID")
        comments: list[dict] = []
        for page in range(3):
            response = client.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "tags": f"comment,story_{story_id}",
                    "hitsPerPage": 50,
                    "page": page,
                },
            )
            response.raise_for_status()
            batch = response.json().get("hits") or []
            comments.extend(batch)
            if len(batch) < 50:
                break
    return dedupe(parse_hn(comments), limit)


def fetch_landing_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text(
            "https://landing.jobs/jobs?query=frontend%20engineer",
            client=client,
            board="Landing.jobs",
        )
    jobs = dedupe(parse_landing(text), limit)
    if not jobs:
        raise ValueError("Landing.jobs did not include job listings on the public page.")
    return jobs


def fetch_relocate_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text(
            "https://relocate.me/international-jobs",
            client=client,
            board="Relocate.me",
        )
    return dedupe(parse_relocate(text), limit)
