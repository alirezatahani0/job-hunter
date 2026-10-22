from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from job_assistant.nodes.write_cover_letter import cover_for, persist_cover, write_cover_letter_for_job
from job_assistant.services.cv_docx import markdown_to_docx
from job_assistant.services.eligibility import is_open_to_applicant
from job_assistant.services.remote import is_remote_job
from job_assistant.state import Job, JobAssistantState

APPLICATIONS_PATH = Path("output") / "applications.json"


def load_applications() -> list[dict]:
    if not APPLICATIONS_PATH.exists():
        return []
    payload = json.loads(APPLICATIONS_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return payload.get("applications") or []


def application_for(job_id: str | None) -> dict | None:
    if not job_id:
        return None
    return next((item for item in load_applications() if item.get("job_id") == job_id), None)


def record_application(record: dict) -> dict:
    APPLICATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    letter = record.get("cover_letter") or ""
    if letter:
        saved_cover = persist_cover(
            {
                "job_id": record.get("job_id"),
                "title": record.get("title"),
                "company": record.get("company"),
                "url": record.get("url"),
                "cv_source": record.get("cv_source"),
                "cover_letter": letter,
                "points_used": record.get("points_used") or [],
                "written_at": record.get("applied_at") or record.get("written_at"),
            }
        )
        record = {**record, "cover_path": saved_cover.get("cover_path")}
    items = [item for item in load_applications() if item.get("job_id") != record.get("job_id")]
    items.insert(0, record)
    APPLICATIONS_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")
    return record


def apply_to_job(
    job: Job,
    *,
    matched: list[str] | None = None,
    cv_source: str = "original",
    cover_letter: str | None = None,
    cv_text: str | None = None,
    submit=None,
) -> dict:
    url = (job.get("url") or "").strip()
    if not url:
        raise ValueError("This listing has no apply URL.")
    if not is_remote_job(job) or not is_open_to_applicant(job):
        raise ValueError(
            "This role is not fully remote for any location. Apply only runs for those jobs."
        )
    letter = (cover_letter or "").strip()
    if not letter:
        existing = cover_for(job.get("id"))
        letter = (existing or {}).get("cover_letter") or ""
    if not letter:
        if not (cv_text or "").strip():
            raise ValueError("No cover letter yet. Write one first (needs ANTHROPIC_API_KEY).")
        drafted = write_cover_letter_for_job(
            job,
            cv_text=cv_text or "",
            cv_source=cv_source,
            matched=matched or list(job.get("matched_skills") or []),
        )
        letter = drafted.get("cover_letter") or ""
    record = {
        "job_id": job.get("id"),
        "title": job.get("title"),
        "company": job.get("company"),
        "url": url,
        "cv_source": cv_source,
        "cover_letter": letter,
        "prepared_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ready",
        "submitted": False,
        "form_phone": os.getenv("APPLICANT_PHONE", "+372 5605 7387").strip(),
    }
    resume = (cv_text or "").strip()
    if resume:
        company = "".join(
            ch if ch.isalnum() or ch in "-_" else "_"
            for ch in str(job.get("company") or "job")
        )[:40]
        resume_path = APPLICATIONS_PATH.parent / f"resume_{company}.docx"
        resume_path.write_bytes(markdown_to_docx(resume))
        record["resume_path"] = str(resume_path)
    saved = record_application(record)
    if submit is None:
        from job_assistant.services.browser_apply import submit_application

        submit = submit_application
    if saved.get("resume_path"):
        outcome = submit(
            url,
            resume_path=saved["resume_path"],
            cover_path=saved.get("cover_path"),
        )
        saved = record_application(
            {
                **saved,
                "submitted": bool(outcome.get("submitted")),
                "status": "submitted" if outcome.get("submitted") else "ready",
                "submit_detail": outcome.get("detail") or "",
                "needs_you": bool(outcome.get("needs_you")),
                "apply_url": outcome.get("apply_url") or url,
            }
        )
    return saved


def apply_job_node(state: JobAssistantState) -> dict:
    job = state.get("selected_job")
    if not job:
        return {
            "cover_letter": state.get("cover_letter") or "",
            "messages": [*state.get("messages", []), "Skipped apply: no selected job."],
        }
    cv_source = "optimized" if (state.get("updated_cv") or "").strip() else "original"
    try:
        saved = apply_to_job(
            job,
            matched=list(job.get("matched_skills") or []),
            cv_source=cv_source,
            cover_letter=state.get("cover_letter") or "",
            cv_text=(state.get("updated_cv") or state.get("base_cv") or ""),
        )
    except ValueError as exc:
        return {
            "cover_letter": state.get("cover_letter") or "",
            "messages": [*state.get("messages", []), f"Skipped apply: {exc}"],
        }
    if saved.get("submitted"):
        msg = (
            f"Submitted {saved.get('title')} @ {saved.get('company')}. "
            f"{saved.get('submit_detail') or ''}"
        )
    else:
        msg = (
            f"Remote application packet ready for {saved.get('title')} @ {saved.get('company')}. "
            f"{saved.get('submit_detail') or 'Employer form is not submitted.'} "
            f"Posting: {saved.get('url')}"
        )
    return {
        "cover_letter": saved.get("cover_letter") or "",
        "application_path": saved.get("cover_path") or "",
        "messages": [*state.get("messages", []), msg],
    }
