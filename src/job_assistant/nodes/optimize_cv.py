from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from job_assistant.services.ats_check import ai_tells_in
from job_assistant.services.cv_loader import strip_private_contact
from job_assistant.services.cv_matcher import extract_cv_profile, skills_in_text
from job_assistant.services.llm import get_llm, invoke_structured
from job_assistant.state import JobAssistantState


class OptimizedCV(BaseModel):
    updated_cv: str = Field(description="Full updated resume in clean markdown")
    changes_made: list[str] = Field(description="Bullet list of important changes")
    keywords_used: list[str] = Field(
        default_factory=list,
        description="JD keywords woven into the resume from real experience",
    )


OPTIMIZE_PROMPT = """You tailor resumes for senior frontend / full-stack engineers.

In ONE pass: match this JD and write it like a human engineer (ATS-safe).

Hard rules:
- Do not invent employers, titles, dates, degrees, tools, or metrics.
- You MAY reorder bullets, tighten wording, and move JD-relevant work higher.
- You MAY echo JD keywords only when they map to real CV experience (see allowed skills).
- Do not claim tools that are not in the original CV or allowed skills list.
- ATS-friendly: single column markdown, standard headings (Summary, Skills, Experience), no tables, no icons.
- Keep email only. Do not include location or phone.
- Target 1–2 pages. Prefer fewer, stronger bullets.
- Each bullet: concrete action; keep numbers from the original.

Human voice:
- Mix short and medium bullets. Do not start every bullet with the same verb.
- Ban: spearheaded, leveraged, utilized, robust, seamless, cutting-edge, results-driven, passionate, synergy, meticulous, "proven track record", "fast-paced environment".
- Summary: 3–4 sentences, specific to this role.

Output JSON keys (required):
- updated_cv: the full resume as markdown (not a key named resume)
- changes_made: array of short strings
- keywords_used: array of JD keywords you used from real experience

Allowed skills from the candidate CV (only these may be emphasized):
{allowed_skills}

Skills that already overlap this JD (lean on these):
{matched_skills}

Original CV:
---
{base_cv}
---

Target job:
Title: {title}
Company: {company}
Tags: {tags}
URL: {url}

Job description:
---
{description}
---
"""


def _strip_ai_tells(text: str) -> str:
    leftover = ai_tells_in(text)
    if not leftover:
        return text
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(p) for p in leftover) + r")\b",
        flags=re.IGNORECASE,
    )
    cleaned = pattern.sub("", text)
    return re.sub(r" +", " ", cleaned)


def _persist(job: dict, updated_cv: str, changes: list[str], keywords: list[str]) -> dict[str, str]:
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "optimized_cv.md"
    json_path = out_dir / "optimized.json"
    cleaned = strip_private_contact(updated_cv)
    md_path.write_text(cleaned + "\n", encoding="utf-8")
    payload = {
        "job": {
            "id": job.get("id"),
            "title": job.get("title"),
            "company": job.get("company"),
            "url": job.get("url"),
            "score": job.get("score"),
        },
        "changes_made": changes,
        "keywords_used": keywords,
        "updated_cv": cleaned,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"md": str(md_path), "json": str(json_path), "cv": cleaned}


def optimize_cv_node(state: JobAssistantState) -> dict:
    job = state.get("selected_job")
    base_cv = state.get("base_cv") or ""
    if not job:
        return {
            "updated_cv": strip_private_contact(base_cv),
            "cv_changes": [],
            "messages": [*state.get("messages", []), "Skipped CV optimize: no selected job."],
        }
    if not base_cv.strip():
        raise ValueError("base_cv is empty; provide a CV via CV_PATH or --cv")

    profile = extract_cv_profile(base_cv)
    jd_skills = skills_in_text(
        " ".join(
            [
                job.get("title") or "",
                " ".join(job.get("tags") or []),
                (job.get("description") or "")[:4000],
            ]
        )
    )
    matched = job.get("matched_skills") or [
        skill for skill in profile.skills if skill in jd_skills
    ]

    llm = get_llm(temperature=0.35)
    prompt = OPTIMIZE_PROMPT.format(
        allowed_skills=", ".join(profile.skills) or "use only skills present in the original CV",
        matched_skills=", ".join(matched) or "none detected — still do not invent skills",
        base_cv=base_cv,
        title=job["title"],
        company=job["company"],
        tags=", ".join(job.get("tags") or []),
        url=job.get("url") or "",
        description=(job.get("description") or "")[:4000],
    )
    tailored = invoke_structured(llm, OptimizedCV, prompt)
    draft = _strip_ai_tells(tailored.updated_cv.strip())
    changes = list(tailored.changes_made or [])
    keywords = list(tailored.keywords_used or [])

    paths = _persist(job, draft, changes, keywords)
    change_preview = "; ".join(changes[:5]) if changes else "n/a"
    msg = (
        f"Optimized CV for {job['title']} @ {job['company']} "
        f"(JD skills used: {', '.join(matched[:8]) or 'n/a'}). "
        f"Changes: {change_preview}. Saved {paths['md']}"
    )
    return {
        "updated_cv": paths["cv"],
        "cv_changes": changes,
        "output_path": paths["md"],
        "messages": [*state.get("messages", []), msg],
    }
