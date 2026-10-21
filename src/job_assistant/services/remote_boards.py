from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import unescape

from job_assistant.services.board_http import (
    clean_html,
    dedupe,
    fetch_text,
    make_job,
    open_client,
)
from job_assistant.state import Job


def parse_weworkremotely(xml_text: str) -> list[Job]:
    root = ET.fromstring(xml_text)
    jobs: list[Job] = []
    for item in root.iter("item"):
        title = unescape((item.findtext("title") or "")).strip()
        link = (item.findtext("link") or "").strip()
        region = unescape((item.findtext("region") or "Remote")).strip()
        category = unescape((item.findtext("category") or "")).strip()
        description = clean_html(unescape(item.findtext("description") or ""))
        if ":" in title:
            company, role = title.split(":", 1)
        else:
            company, role = "Unknown", title
        location = region if "remote" in region.lower() or "anywhere" in region.lower() else f"Remote, {region}"
        jobs.append(
            make_job(
                source="weworkremotely",
                job_id=link.rstrip("/").split("/")[-1] or role,
                title=role,
                company=company,
                location=location,
                url=link,
                tags=[category] if category else [],
                description=description,
            )
        )
    return jobs


def parse_fourdayweek(html: str) -> list[Job]:
    pattern = re.compile(
        r'\\"id\\":\\"([^\\"]+)\\",\\"slug\\":\\"([^\\"]*)\\",\\"title\\":\\"([^\\"]+)\\",\\"companyName\\":\\"([^\\"]*)\\"'
    )
    jobs: list[Job] = []
    for match in pattern.finditer(html):
        job_id, slug, title, company = match.groups()
        window = html[match.end() : match.end() + 700]
        if "Remote" not in window and "remote" not in window:
            continue
        place = "Remote"
        located = re.search(r"Remote · ([^\"\\<]{2,80})", window)
        if located:
            place = f"Remote, {located.group(1).strip()}"
        url_slug = slug or job_id
        jobs.append(
            make_job(
                source="fourdayweek",
                job_id=job_id,
                title=unescape(title),
                company=unescape(company) or "Undisclosed",
                location=place,
                url=f"https://4dayweek.io/job/{url_slug}",
            )
        )
    return jobs


def parse_fourdayweek_api(payload: dict) -> list[Job]:
    jobs: list[Job] = []
    for item in payload.get("jobs") or []:
        if not isinstance(item, dict):
            continue
        if item.get("work_arrangement") != "remote":
            continue
        places = []
        for place in item.get("locations") or []:
            if isinstance(place, dict):
                bits = [place.get("city"), place.get("country")]
                text = ", ".join(str(bit) for bit in bits if bit)
                if text:
                    places.append(text)
        where = places[0] if places else ""
        location = f"Remote, {where}" if where else "Remote"
        slug = str(item.get("slug") or item.get("id") or "")
        company = str(item.get("company_name") or "").strip()
        if not company:
            company = f"Undisclosed {str(item.get('id') or '')[:8]}".strip()
        jobs.append(
            make_job(
                source="fourdayweek",
                job_id=str(item.get("id") or slug),
                title=str(item.get("title") or ""),
                company=company,
                location=location,
                url=f"https://4dayweek.io/job/{slug}",
                tags=[str(tag.get("name")) for tag in (item.get("stack") or []) if isinstance(tag, dict)],
            )
        )
    return jobs


def parse_justremote(html: str) -> list[Job]:
    jobs: list[Job] = []
    for href, title in re.findall(
        r'href="(https://justremote\.co/remote-[^"]+)"[^>]*>\s*([^<]{4,140})',
        html,
    ):
        if href.rstrip("/").endswith("-jobs"):
            continue
        jobs.append(
            make_job(
                source="justremote",
                job_id=href.rstrip("/").split("/")[-1],
                title=unescape(title),
                company="JustRemote",
                location="Remote",
                url=href,
            )
        )
    return jobs


def parse_workingnomads(payload: list) -> list[Job]:
    jobs: list[Job] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        tags = str(item.get("tags") or "")
        tag_list = [part.strip() for part in tags.split(",") if part.strip()]
        location = str(item.get("location") or "Remote")
        if "remote" not in location.lower():
            location = f"Remote, {location}"
        url = str(item.get("url") or "")
        jobs.append(
            make_job(
                source="workingnomads",
                job_id=url.rstrip("/").split("/")[-1] or str(item.get("title")),
                title=str(item.get("title") or ""),
                company=str(item.get("company_name") or "Unknown"),
                location=location,
                url=url,
                tags=tag_list,
                description=clean_html(str(item.get("description") or "")),
            )
        )
    return jobs


def parse_euremote(html: str) -> list[Job]:
    jobs: list[Job] = []
    for href, inner in re.findall(
        r'<a[^>]+href="(https://euremotejobs\.com/job/[^"]+)"[^>]*>(.*?)</a>',
        html,
        re.S,
    ):
        title_match = re.search(r"<h[123][^>]*>\s*([^<]+)", inner)
        company_match = re.search(r'class="[^"]*company[^"]*"[^>]*>\s*(?:<strong>)?\s*([^<]+)', inner)
        alt = re.search(r'alt="([^"]+)"', inner)
        title = title_match.group(1).strip() if title_match else ""
        if not title:
            slug = href.rstrip("/").split("/")[-1]
            words = [word for word in slug.split("-") if word]
            title = " ".join(words[-4:]).title()
        company = "Unknown"
        if company_match and company_match.group(1).strip():
            company = company_match.group(1).strip()
        elif alt:
            company = alt.group(1).strip()
        jobs.append(
            make_job(
                source="euremote",
                job_id=href.rstrip("/").split("/")[-1],
                title=unescape(title),
                company=unescape(company),
                location="Remote, Europe",
                url=href,
            )
        )
    return jobs


def parse_dynamite(html: str) -> list[Job]:
    jobs: list[Job] = []
    for href, title in re.findall(
        r'href="(https://dynamitejobs\.com/(?:remote-)?jobs/[^"]+)"[^>]*>\s*([^<]{4,140})',
        html,
    ):
        if href.rstrip("/").endswith("/engineering") or href.rstrip("/").endswith("/remote-jobs"):
            continue
        jobs.append(
            make_job(
                source="dynamite",
                job_id=href.rstrip("/").split("/")[-1],
                title=unescape(title),
                company="Dynamite Jobs",
                location="Remote",
                url=href,
            )
        )
    return jobs


def fetch_weworkremotely_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text(
            "https://weworkremotely.com/categories/remote-programming-jobs.rss",
            client=client,
            board="We Work Remotely",
        )
    return dedupe(parse_weworkremotely(text), limit)


def fetch_fourdayweek_jobs(*, limit: int = 40) -> list[Job]:
    jobs: list[Job] = []
    with open_client() as client:
        for query in ("frontend", "fullstack", "react"):
            response = client.get(
                "https://4dayweek.io/api/jobs",
                params={"category": "engineering", "work_arrangement": "remote", "q": query},
            )
            response.raise_for_status()
            jobs.extend(parse_fourdayweek_api(response.json()))
    return dedupe(jobs, limit)


def fetch_justremote_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text(
            "https://justremote.co/remote-developer-jobs",
            client=client,
            board="JustRemote",
        )
    jobs = dedupe(parse_justremote(text), limit)
    if not jobs:
        raise ValueError("JustRemote did not include job listings on the public page.")
    return jobs


def fetch_workingnomads_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        response = client.get("https://www.workingnomads.com/api/exposed_jobs/")
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Working Nomads returned an unexpected response.")
    return dedupe(parse_workingnomads(payload), limit)


def fetch_euremote_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text(
            "https://euremotejobs.com/job-region/remote-jobs-europe/",
            client=client,
            board="EU Remote Jobs",
        )
    return dedupe(parse_euremote(text), limit)


def fetch_dynamite_jobs(*, limit: int = 40) -> list[Job]:
    with open_client() as client:
        text = fetch_text(
            "https://dynamitejobs.com/remote-jobs/engineering",
            client=client,
            board="Dynamite Jobs",
        )
    jobs = dedupe(parse_dynamite(text), limit)
    if not jobs:
        raise ValueError("Dynamite Jobs did not include job listings on the public page.")
    return jobs
