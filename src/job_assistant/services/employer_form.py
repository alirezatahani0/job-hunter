from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

APPLY_LINKS_PATH = Path("output") / "apply_links.json"
DOVER_SUBMIT_URL = "https://app.dover.com/api/v1/inbound/application-portal-inbound-application"
HIMALAYAS_APPLY_LINK = "https://himalayas.app/api/jobs/apply-link"

APPLICANT_FIRST = "Alireza"
APPLICANT_LAST = "Tahani"
APPLICANT_EMAIL = "alireza.tahani01@gmail.com"
APPLICANT_LINKEDIN = "https://www.linkedin.com/in/alirezatahani"
APPLICANT_CITY = "Sofia"
APPLICANT_COUNTRY = "Bulgaria"


def applicant_phone() -> str:
    return os.getenv("APPLICANT_PHONE", "+372 5605 7387").strip()


def classify_apply_url(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    if "dover.com" in host:
        return "dover"
    if "recruitee.com" in host:
        return "recruitee"
    if "wellfound.com" in host or "angel.co" in host:
        return "wellfound"
    if "himalayas.app" in host:
        return "himalayas"
    if host:
        return "other"
    return "missing"


def dover_job_id(url: str) -> str | None:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) >= 3 and parts[0] == "apply":
        return parts[2]
    return None


def himalayas_company_slug(url: str) -> tuple[str, str] | None:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) >= 4 and parts[0] == "companies" and parts[2] == "jobs":
        return parts[1], parts[3]
    return None


def load_apply_links() -> dict[str, str]:
    if not APPLY_LINKS_PATH.exists():
        return {}
    payload = json.loads(APPLY_LINKS_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return {str(key): str(value) for key, value in payload.items() if value}
    return {}


def remember_apply_link(posting_url: str, apply_url: str) -> None:
    if not posting_url or not apply_url or posting_url == apply_url:
        return
    links = load_apply_links()
    links[posting_url] = apply_url
    APPLY_LINKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPLY_LINKS_PATH.write_text(json.dumps(links, indent=2), encoding="utf-8")


def resolve_apply_url(posting_url: str, client) -> str | None:
    """Follow a board posting to the employer form. Himalayas hides that link until sign-in."""
    cached = load_apply_links().get(posting_url)
    if cached:
        return cached
    kind = classify_apply_url(posting_url)
    if kind in {"dover", "recruitee", "wellfound", "other"}:
        return posting_url
    if kind != "himalayas":
        return None
    parsed = himalayas_company_slug(posting_url)
    if parsed is None:
        return None
    company, slug = parsed
    response = client.get(
        HIMALAYAS_APPLY_LINK,
        params={"company": company, "slug": slug},
    )
    link = ""
    if response.status_code == 200:
        payload = response.json()
        if isinstance(payload, dict):
            link = (payload.get("applicationLink") or "").strip()
    if not link:
        return None
    followed = client.get(link)
    final = str(followed.url)
    remember_apply_link(posting_url, final)
    return final


def pick_location(options: list[dict], *, city: str = APPLICANT_CITY, country: str = APPLICANT_COUNTRY) -> dict | None:
    """Choose the work-location answer that matches Sofia, Bulgaria."""
    city_name = city.lower()
    country_name = country.lower()
    labeled = [option for option in options if (option.get("label") or "").strip()]
    for option in labeled:
        label = option["label"].lower()
        if city_name in label and country_name in label:
            return option
    for option in labeled:
        if country_name in option["label"].lower():
            return option
    return None


def dover_fields(*, job_id: str, referrer: str = "himalayas.app") -> dict[str, str]:
    return {
        "job_id": job_id,
        "referrer_source": referrer,
        "first_name": APPLICANT_FIRST,
        "last_name": APPLICANT_LAST,
        "email": APPLICANT_EMAIL,
        "linkedin_url": APPLICANT_LINKEDIN,
        "phone_number": applicant_phone(),
    }


def failed(step: str, detail: str, *, needs_you: bool = False, apply_url: str = "") -> dict:
    return {
        "submitted": False,
        "needs_you": needs_you,
        "step": step,
        "detail": detail,
        "apply_url": apply_url,
    }


def succeeded(detail: str, *, apply_url: str = "") -> dict:
    return {
        "submitted": True,
        "needs_you": False,
        "step": "submitted",
        "detail": detail,
        "apply_url": apply_url,
    }
