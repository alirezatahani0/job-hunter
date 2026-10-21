from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from job_assistant.services.llm import get_llm, invoke_structured
from job_assistant.state import Job, JobAssistantState

APPLICANT_NAME = "Alireza Tahani"
APPLICANT_EMAIL = "alireza.tahani01@gmail.com"
APPLICANT_PHONE = os.getenv("APPLICANT_PHONE", "+372 5605 7387").strip()
COVER_LETTERS_PATH = Path("output") / "cover_letters.json"

COVER_PROMPT = """Write a short job cover letter for a senior frontend / full-stack engineer.

Hard rules:
- Only use facts from the CV. Do not invent employers, titles, dates, tools, metrics, or domain experience.
- Do not claim healthcare, HIPAA, RCM, or in-house production LLM work at SAP or Identity Global.
- Cursor / Claude daily use and the personal LangGraph Job Assistant (Claude API, structured JSON) may be mentioned only if they help this JD.
- 3–5 short paragraphs. No bullet list unless the JD asks for one.
- Specific to this company and title. No generic "I am passionate" filler.
- Ban: spearheaded, leveraged, utilized, robust, seamless, cutting-edge, results-driven, synergy, "proven track record", "fast-paced environment".
- Sign off as {name} with email {email}. Do not include a phone number, city, or country.

Output JSON keys (required):
- cover_letter: the full letter as plain text (not markdown headings)
- points_used: short strings of CV facts you actually used

Matched skills already on the CV (lean on these):
{matched_skills}

CV:
---
{cv}
---

Target job:
Title: {title}
Company: {company}
URL: {url}

Job description:
---
{description}
---
"""


class CoverLetterDraft(BaseModel):
    cover_letter: str = Field(description="Full cover letter as plain text")
    points_used: list[str] = Field(
        default_factory=list,
        description="CV facts used in the letter",
    )


def load_cover_letters() -> list[dict]:
    if not COVER_LETTERS_PATH.exists():
        return []
    payload = json.loads(COVER_LETTERS_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return payload.get("letters") or []


def cover_for(job_id: str | None) -> dict | None:
    if not job_id:
        return None
    return next((item for item in load_cover_letters() if item.get("job_id") == job_id), None)


def finish_letter(letter: str) -> str:
    """Sign off with name and email. The phone number is for forms, not this letter."""
    kept: list[str] = []
    for raw in (letter or "").splitlines():
        if APPLICANT_PHONE in raw:
            raw = raw.replace(APPLICANT_PHONE, "")
        label = raw.strip(" :*-")
        if label.lower() in {"phone", "mobile", "tel", "telephone", "cell"}:
            continue
        if not raw.strip():
            kept.append("")
            continue
        kept.append(raw.rstrip())
    text = "\n".join(kept).strip()
    missing = []
    if APPLICANT_NAME not in text:
        missing.append(APPLICANT_NAME)
    if APPLICANT_EMAIL not in text:
        missing.append(APPLICANT_EMAIL)
    if missing:
        text = f"{text}\n\n" + "\n".join(missing)
    return text.strip()


def letter_to_docx(letter: str) -> bytes:
    from job_assistant.services.cv_docx import markdown_to_docx

    return markdown_to_docx(finish_letter(letter))


def persist_cover(record: dict) -> dict:
    COVER_LETTERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    company = "".join(
        ch if ch.isalnum() or ch in "-_" else "_"
        for ch in str(record.get("company") or "job")
    )[:40]
    job_bit = "".join(
        ch if ch.isalnum() or ch in "-_" else "_"
        for ch in str(record.get("job_id") or "")
    )[:48]
    stem = f"cover_{company}_{job_bit}" if job_bit else f"cover_{company}"
    letter = finish_letter(record.get("cover_letter") or "")
    letter_path = COVER_LETTERS_PATH.parent / f"{stem}.docx"
    letter_path.write_bytes(letter_to_docx(letter))
    md_path = letter_path.with_suffix(".md")
    if md_path.exists():
        md_path.unlink()
    record = {**record, "cover_letter": letter, "cover_path": str(letter_path)}
    items = [item for item in load_cover_letters() if item.get("job_id") != record.get("job_id")]
    items.insert(0, record)
    COVER_LETTERS_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return record


def write_cover_letter_for_job(
    job: Job,
    *,
    cv_text: str,
    cv_source: str = "original",
    matched: list[str] | None = None,
) -> dict:
    skills = matched or list(job.get("matched_skills") or [])
    llm = get_llm(temperature=0.4)
    prompt = COVER_PROMPT.format(
        name=APPLICANT_NAME,
        email=APPLICANT_EMAIL,
        matched_skills=", ".join(skills[:10]) or "TypeScript, React, Node.js",
        cv=cv_text.strip()[:8000],
        title=job.get("title") or "this role",
        company=job.get("company") or "the company",
        url=job.get("url") or "",
        description=(job.get("description") or "")[:3500],
    )
    draft = invoke_structured(llm, CoverLetterDraft, prompt)
    letter = finish_letter(draft.cover_letter or "")
    record = {
        "job_id": job.get("id"),
        "title": job.get("title"),
        "company": job.get("company"),
        "url": job.get("url"),
        "cv_source": cv_source,
        "cover_letter": letter,
        "points_used": list(draft.points_used or []),
        "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return persist_cover(record)


def write_cover_letter_node(state: JobAssistantState) -> dict:
    job = state.get("selected_job")
    if not job:
        return {
            "cover_letter": "",
            "messages": [*state.get("messages", []), "Skipped cover letter: no selected job."],
        }
    tailored = (state.get("updated_cv") or "").strip()
    cv_text = tailored or (state.get("base_cv") or "")
    if not cv_text.strip():
        raise ValueError("No CV in state to write a cover letter from.")
    cv_source = "optimized" if tailored else "original"
    saved = write_cover_letter_for_job(
        job,
        cv_text=cv_text,
        cv_source=cv_source,
        matched=list(job.get("matched_skills") or []),
    )
    msg = (
        f"Wrote cover letter for {saved.get('title')} @ {saved.get('company')}. "
        f"Saved {saved.get('cover_path')}."
    )
    return {
        "cover_letter": saved.get("cover_letter") or "",
        "application_path": saved.get("cover_path") or "",
        "messages": [*state.get("messages", []), msg],
    }
