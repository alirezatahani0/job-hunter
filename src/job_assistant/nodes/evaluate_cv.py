from __future__ import annotations

from pydantic import BaseModel, Field

from job_assistant.services.llm import get_llm, invoke_structured
from job_assistant.state import EvaluationScores, JobAssistantState


class CVEvaluation(BaseModel):
    jd_relevance: float = Field(ge=0, le=100, description="How well CV matches the JD")
    human_readability: float = Field(ge=0, le=100, description="Clarity for human readers")
    format_quality: float = Field(ge=0, le=100, description="Structure, consistency, length")
    ats_score: float = Field(ge=0, le=100, description="Likelihood to pass ATS parsing/keyword match")
    ats_pass: bool = Field(description="True if ATS would likely accept/pass this CV")
    ai_detected: bool = Field(
        description="True if CV reads like obvious AI-generated boilerplate that ATS/AI detectors may flag"
    )
    overall: float = Field(ge=0, le=100, description="Weighted overall quality score")
    feedback: list[str] = Field(description="Actionable improvement notes")


EVAL_PROMPT = """You are a strict resume reviewer combining recruiter + ATS perspectives.

Score the UPDATED CV against the job description.

Scoring guidance:
- jd_relevance: keyword alignment, role fit, evidenced skills (not claimed-only)
- human_readability: natural tone, scannable bullets, concrete impact
- format_quality: headings, consistency, no tables/graphics issues for ATS
- ats_score: parseability + relevant keyword coverage without stuffing
- ats_pass: true only if ats_score >= 70 and format is clean
- ai_detected: true if language is generic, repetitive, over-polished AI clichés
- overall: weighted blend emphasizing relevance and ATS (relevance 35%, ATS 25%, readability 20%, format 20%)

Return scores 0-100.

Job:
Title: {title}
Company: {company}
Tags: {tags}

Job description:
---
{description}
---

Updated CV:
---
{updated_cv}
---
"""


def evaluate_cv_node(state: JobAssistantState) -> dict:
    job = state.get("selected_job")
    updated_cv = state.get("updated_cv") or ""
    if not job or not updated_cv.strip():
        return {
            "evaluation": None,
            "messages": [*state.get("messages", []), "Skipped evaluate: missing job or CV."],
        }

    llm = get_llm(temperature=0.0)
    prompt = EVAL_PROMPT.format(
        title=job["title"],
        company=job["company"],
        tags=", ".join(job.get("tags") or []),
        description=(job.get("description") or "")[:8000],
        updated_cv=updated_cv[:12000],
    )
    result = invoke_structured(llm, CVEvaluation, prompt)
    evaluation: EvaluationScores = {
        "jd_relevance": result.jd_relevance,
        "human_readability": result.human_readability,
        "format_quality": result.format_quality,
        "ats_score": result.ats_score,
        "ats_pass": result.ats_pass,
        "ai_detected": result.ai_detected,
        "overall": result.overall,
        "feedback": result.feedback,
    }
    msg = (
        f"Evaluation overall={evaluation['overall']:.1f} "
        f"ATS={'PASS' if evaluation['ats_pass'] else 'FAIL'} "
        f"AI_flag={'yes' if evaluation['ai_detected'] else 'no'}"
    )
    return {
        "evaluation": evaluation,
        "messages": [*state.get("messages", []), msg],
    }
