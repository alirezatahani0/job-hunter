from __future__ import annotations

from pydantic import BaseModel, Field

from job_assistant.services.llm import get_llm, invoke_structured
from job_assistant.state import JobAssistantState


class OptimizedCV(BaseModel):
    updated_cv: str = Field(description="Full updated resume in clean markdown")
    changes_made: list[str] = Field(description="Bullet list of important changes")


OPTIMIZE_PROMPT = """You are an expert resume writer helping a candidate tailor their CV to one job.

Rules:
- Keep facts truthful; do not invent employers, degrees, or fake metrics.
- Reorder and rephrase to emphasize JD-relevant skills and impact.
- Mirror important keywords from the JD naturally (for ATS), without keyword stuffing.
- Keep format ATS-friendly: simple markdown headings, bullets, no tables/columns.
- Make it sound human: varied sentence rhythm, concrete verbs, no buzzword soup.
- Preserve contact section if present.
- Length: roughly same as original (or slightly tighter).

Original CV:
---
{base_cv}
---

Target job:
Title: {title}
Company: {company}
Location: {location}
Tags: {tags}
Salary: {salary}
URL: {url}

Job description:
---
{description}
---
"""


def optimize_cv_node(state: JobAssistantState) -> dict:
    job = state.get("selected_job")
    base_cv = state.get("base_cv") or ""
    if not job:
        return {
            "updated_cv": base_cv,
            "messages": [*state.get("messages", []), "Skipped CV optimize: no selected job."],
        }
    if not base_cv.strip():
        raise ValueError("base_cv is empty; provide a CV via CV_PATH or --cv")

    llm = get_llm(temperature=0.4)
    prompt = OPTIMIZE_PROMPT.format(
        base_cv=base_cv,
        title=job["title"],
        company=job["company"],
        location=job["location"],
        tags=", ".join(job.get("tags") or []),
        salary=job.get("salary_text") or "not listed",
        url=job.get("url") or "",
        description=(job.get("description") or "")[:8000],
    )
    result = invoke_structured(llm, OptimizedCV, prompt)
    changes = "; ".join(result.changes_made[:5]) if result.changes_made else "n/a"
    msg = f"Optimized CV for {job['title']} @ {job['company']}. Changes: {changes}"
    return {
        "updated_cv": result.updated_cv.strip(),
        "messages": [*state.get("messages", []), msg],
    }
