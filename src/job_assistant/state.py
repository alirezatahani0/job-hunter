from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class Job(TypedDict):
    id: str
    title: str
    company: str
    location: str
    tags: list[str]
    salary_min: int | None
    salary_max: int | None
    salary_text: str | None
    url: str
    description: str
    category: NotRequired[str]
    source: NotRequired[str]
    hiring_timezones: NotRequired[str]
    location_requirements: NotRequired[str]
    score: NotRequired[float]


class EvaluationScores(TypedDict):
    jd_relevance: float
    human_readability: float
    format_quality: float
    ats_score: float
    ats_pass: bool
    ai_detected: bool
    overall: float
    feedback: list[str]


class JobAssistantState(TypedDict):
    """Shared graph state for the job assistant workflow."""

    # Inputs
    preferences: dict[str, Any]
    base_cv: str
    max_jobs: int

    # Node outputs
    jobs: list[Job]
    sorted_jobs: list[Job]
    selected_job: Job | None
    updated_cv: str
    evaluation: EvaluationScores | None
    output_path: str
    messages: list[str]
