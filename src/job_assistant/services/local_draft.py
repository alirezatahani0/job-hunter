"""Resume and cover letter written from the CV. No outside model is called."""

from __future__ import annotations

import re

APPLICANT_NAME = "Alireza Tahani"
APPLICANT_EMAIL = "alireza.tahani01@gmail.com"

_SUMMARY = re.compile(
    r"(## Professional Summary\n\n)(.*?)(\n\n## )",
    re.DOTALL,
)
_DO_NOT_CLAIM = (
    "react native",
    "nestjs",
    "nest.js",
    "prisma",
    "postgresql",
    "postgres",
    "supabase",
    "stripe",
    "vue",
    "golang",
    "kafka",
    "python",
    "electron",
    "tauri",
    "hipaa",
    "healthcare",
)


def role_label(title: str) -> str:
    """Use the posting title only when it does not name a skill the CV lacks."""
    low = (title or "").lower()
    if not low.strip() or any(word in low for word in _DO_NOT_CLAIM):
        return "this role"
    return title.strip()


def draft_resume(base_cv: str, job: dict, matched: list[str]) -> tuple[str, list[str], list[str]]:
    """Lead the summary with skills the CV already has. Leave the rest of the CV as written."""
    cv = base_cv.strip()
    lead = [skill for skill in matched if skill.lower() in cv.lower()][:6]
    if not lead:
        lead = [skill for skill in ("TypeScript", "React", "Node.js") if skill.lower() in cv.lower()]
    label = role_label(str(job.get("title") or ""))
    company = str(job.get("company") or "this company").strip()
    summary = (
        f"Senior full-stack engineer (9+ years) for {label}. "
        f"Skills already on this CV that match the posting: {', '.join(lead) or 'TypeScript, React, Node.js'}. "
        "Current work is lead front-end on a trading platform: a 200ms live market refresh, "
        "Web Workers, Zod validation, and Lighthouse scores of 90+."
    )
    updated, count = _SUMMARY.subn(lambda match: match.group(1) + summary + match.group(3), cv, count=1)
    if count == 0:
        return cv, ["Left the CV as written."], lead
    change = f"Opened the summary with CV skills that match {label} at {company}."
    return updated, [change], lead


def _bullets(cv: str) -> list[str]:
    return [line.strip()[2:].strip() for line in cv.splitlines() if line.strip().startswith("- ")]


def draft_cover(cv: str, job: dict, matched: list[str]) -> tuple[str, list[str]]:
    """Short first-person letter. Facts come from CV bullets, not from the job description."""
    label = role_label(str(job.get("title") or ""))
    company = str(job.get("company") or "your team").strip() or "your team"
    lead = [skill for skill in matched if skill.lower() in cv.lower()][:4]
    if not lead:
        lead = [skill for skill in ("TypeScript", "React", "Node.js") if skill.lower() in cv.lower()]
    overlap = ", ".join(lead) or "TypeScript, React, and Node.js"
    ranked = sorted(
        _bullets(cv),
        key=lambda bullet: sum(skill.lower() in bullet.lower() for skill in lead),
        reverse=True,
    )
    chosen = [bullet for bullet in ranked if any(skill.lower() in bullet.lower() for skill in lead)][:2]
    if not chosen:
        chosen = ranked[:2]
    work = " ".join(chosen) if chosen else (
        "I have spent nine years shipping TypeScript, React, and Node.js products."
    )
    letter = (
        f"Hello,\n\n"
        f"I'm applying for the {label} role at {company}. "
        f"I'm a senior full-stack engineer, and the overlap with what I already do is {overlap}.\n\n"
        f"{work}\n\n"
        f"I can start immediately.\n\n"
        f"{APPLICANT_NAME}\n"
        f"{APPLICANT_EMAIL}"
    )
    return letter, chosen
