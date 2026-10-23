from __future__ import annotations

import re

from job_assistant.services.remote import is_remote_job
from job_assistant.state import Job

_US_EXACT_LOCATIONS = {
    "us",
    "usa",
    "u.s.",
    "u.s.a.",
    "united states",
    "united states of america",
}

_US_PHRASES = (
    "united states only",
    "us only",
    "usa only",
    "u.s. only",
    "remote - united states",
    "remote, united states",
    "remote (united states)",
    "remote - us",
    "remote, us",
    "remote (us)",
    "remote us",
    "us remote",
    "usa remote",
    "authorized to work in the united states",
    "authorized to work in the us",
    "work authorization in the united states",
    "must be located in the united states",
    "must be located in the us",
    "must reside in the united states",
    "located in the united states",
    "us citizen",
    "u.s. citizen",
    "us based",
    "u.s. based",
    "us-based",
)

_OTHER_REGIONS = (
    "worldwide",
    "anywhere",
    "europe",
    "united kingdom",
    "germany",
    "canada",
    "global",
)

_TARGET_ROLES = (
    "frontend",
    "front-end",
    "front end",
    "full-stack",
    "fullstack",
    "full stack",
    "react",
)

_REJECT_TITLES = (
    "designer",
    "product manager",
    "recruiter",
    "marketing",
)


def _blob(job: Job) -> str:
    parts = [
        job.get("location") or "",
        job.get("location_requirements") or "",
        job.get("hiring_timezones") or "",
        job.get("title") or "",
        job.get("salary_text") or "",
        " ".join(job.get("tags") or []),
        (job.get("description") or "")[:4000],
    ]
    return " ".join(str(part) for part in parts).lower()


def _location_is_us_only(location: str) -> bool:
    if location in _US_EXACT_LOCATIONS:
        return True
    if not re.search(r"\b(united states|u\.s\.a\.|usa)\b", location):
        return False
    if any(token in location for token in _OTHER_REGIONS):
        return False
    if re.search(r"\buk\b", location):
        return False
    return True


def is_us_restricted(job: Job) -> bool:
    """True when the role is limited to the United States."""
    location = (job.get("location") or "").strip().lower()
    if _location_is_us_only(location):
        return True
    blob = _blob(job)
    return any(phrase in blob for phrase in _US_PHRASES)


def pays_with_crypto(job: Job) -> bool:
    """True when the listing pays in crypto. The word cryptography does not count."""
    blob = _blob(job)
    if re.search(r"\bcrypto(?!graphy)\b", blob):
        return True
    return re.search(r"\b(usdc|usdt|bitcoin|btc|ethereum)\b", blob) is not None


_FREE_PLACES = (
    "100 percent remote",
    "100% remote",
    "work from anywhere",
    "work from home",
    "all countries",
    "any country",
    "all locations",
    "any location",
    "all timezones",
    "any timezone",
    "location independent",
    "fully remote",
    "full remote",
    "world wide",
    "worldwide",
    "anywhere",
    "international",
    "global",
    "remote",
    "wfh",
    "distributed",
)

_PLACE_LOCKS = (
    "must be based",
    "must be located",
    "must reside",
    "must live in",
    "eligible countries",
    "following countries",
    "only open to candidates",
    "candidates must be located",
    "applicants must be located",
    "europe only",
    "eu only",
    "eea only",
    "emea only",
    "within europe",
    "within the eu",
    "remote within",
)


def _place_text(job: Job) -> str:
    return " ".join(
        [
            job.get("location") or "",
            job.get("location_requirements") or "",
            job.get("hiring_timezones") or "",
        ]
    ).lower()


def _description_locks_place(job: Job) -> bool:
    text = (job.get("description") or "")[:2500].lower()
    if any(phrase in text for phrase in _PLACE_LOCKS):
        return True
    match = re.search(r"\blocations?\s*:\s*([^\n.]{0,180})", text)
    if not match:
        return False
    tail = match.group(1)
    return not any(token in tail for token in ("worldwide", "anywhere", "global", "all countries"))


def is_open_to_applicant(job: Job) -> bool:
    """Fully remote roles that hire from any location. A country, region, or timezone limit does not qualify."""
    timezones = (job.get("hiring_timezones") or "").strip().lower()
    if timezones and "all timezone" not in timezones and timezones not in {"worldwide", "anywhere", "global"}:
        return False
    compact = _place_text(job)
    for phrase in sorted(_FREE_PLACES, key=len, reverse=True):
        compact = compact.replace(phrase, " ")
    compact = re.sub(r"[^a-z0-9\s]", " ", compact)
    if " ".join(compact.split()):
        return False
    return not _description_locks_place(job)


_WRONG_SPECIALTIES = (
    "backend",
    "back-end",
    "back end",
    "react native",
    "react-native",
    "ios",
    "android",
    "mobile",
)


def is_target_role(job: Job) -> bool:
    title = (job.get("title") or "").lower()
    if any(token in title for token in _REJECT_TITLES):
        return False
    frontend = any(token in title for token in ("frontend", "front-end", "front end"))
    if any(token in title for token in _WRONG_SPECIALTIES) and not frontend:
        return False
    return any(token in title for token in _TARGET_ROLES)


def is_unpaid(job: Job) -> bool:
    """Volunteer and unpaid roles are not applications."""
    blob = f"{job.get('title') or ''} {job.get('description') or ''}".lower()
    return any(token in blob for token in ("volunteer", "unpaid", "pro bono"))


_CLOSED_COUNTRIES = (
    "argentina",
    "india",
    "colombia",
    "mexico",
    "pakistan",
    "philippines",
)


def is_closed_country_list(job: Job) -> bool:
    """A fixed country list that does not include Bulgaria or Europe."""
    blob = _blob(job)
    if any(token in blob for token in ("worldwide", "europe", "bulgaria", "sofia", "anywhere", "global")):
        return False
    hits = sum(1 for name in _CLOSED_COUNTRIES if name in blob)
    return hits >= 3


def choose_board_jobs(
    jobs: list[Job],
    existing_urls: set[str],
    *,
    limit: int | None = None,
    min_score: float = 0.5,
) -> tuple[list[Job], dict[str, int]]:
    """Keep every good frontend/full-stack remote match. Crypto pay ranks first."""
    stats = {
        "dropped_us": 0,
        "dropped_role": 0,
        "dropped_remote": 0,
        "dropped_region": 0,
        "dropped_existing": 0,
        "dropped_company": 0,
        "dropped_score": 0,
        "dropped_unpaid": 0,
        "chosen": 0,
    }
    known = {url.strip() for url in existing_urls if url and url.strip()}
    eligible: list[Job] = []
    for job in jobs:
        if is_us_restricted(job):
            stats["dropped_us"] += 1
            continue
        if not is_remote_job(job):
            stats["dropped_remote"] += 1
            continue
        if not is_open_to_applicant(job):
            stats["dropped_region"] += 1
            continue
        if not is_target_role(job):
            stats["dropped_role"] += 1
            continue
        if is_unpaid(job):
            stats["dropped_unpaid"] += 1
            continue
        if is_closed_country_list(job):
            stats["dropped_region"] += 1
            continue
        url = (job.get("url") or "").strip()
        if url and url in known:
            stats["dropped_existing"] += 1
            continue
        score = job.get("score")
        if not isinstance(score, (int, float)) or score <= min_score:
            stats["dropped_score"] += 1
            continue
        eligible.append(job)

    eligible.sort(
        key=lambda item: (
            1 if pays_with_crypto(item) else 0,
            item.get("score") or 0,
            len(item.get("matched_skills") or []),
        ),
        reverse=True,
    )
    chosen: list[Job] = []
    seen_companies: set[str] = set()
    for job in eligible:
        company = (job.get("company") or "").strip().lower()
        if company and company in seen_companies:
            stats["dropped_company"] += 1
            continue
        if company:
            seen_companies.add(company)
        chosen.append(job)
        if limit is not None and len(chosen) >= limit:
            break
    stats["chosen"] = len(chosen)
    return chosen, stats


def card_name(job: Job) -> str:
    title = (job.get("title") or "Role").strip()
    company = (job.get("company") or "Company").strip()
    return f"{title} — {company}"


def card_description(job: Job) -> str:
    score = job.get("score")
    match = f"{score * 100:.0f}%" if isinstance(score, (int, float)) else "n/a"
    pay = "Crypto" if pays_with_crypto(job) else "Posted range"
    lines = [
        f"URL: {job.get('url') or ''}",
        f"Company: {job.get('company') or ''}",
        f"Location: {job.get('location') or ''}",
        f"Source: {job.get('source') or ''}",
        f"Match: {match}",
        f"Pay: {pay}",
        f"Salary: {job.get('salary_text') or 'not listed'}",
        "",
        (job.get("description") or "")[:800],
    ]
    return "\n".join(lines).strip()
