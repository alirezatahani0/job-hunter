from __future__ import annotations

from job_assistant.nodes.fetch_jobs import persist_jobs
from job_assistant.services.cv_matcher import extract_cv_profile, score_job_against_cv
from job_assistant.state import Job, JobAssistantState


def sort_jobs_node(state: JobAssistantState) -> dict:
    """Rank fetched jobs by overlap with the candidate CV and skills."""
    prefs = state.get("preferences") or {}
    jobs = list(state.get("jobs") or [])
    profile = extract_cv_profile(state.get("base_cv") or "")

    scored: list[Job] = []
    for job in jobs:
        item = dict(job)
        breakdown = score_job_against_cv(job, profile)
        item["score"] = breakdown["score"]
        item["matched_skills"] = breakdown["matched_skills"]
        item["score_breakdown"] = {
            "skill": breakdown["skill_score"],
            "role": breakdown["role_score"],
            "penalty": breakdown["penalty"],
            "missing_core_skills": breakdown["missing_core_skills"],
            "reasons": breakdown["reasons"],
        }
        scored.append(item)  # type: ignore[arg-type]

    scored.sort(
        key=lambda j: (
            j.get("score") or 0,
            len(j.get("matched_skills") or []),
            j.get("salary_max") or j.get("salary_min") or 0,
        ),
        reverse=True,
    )
    selected = scored[0] if scored else None
    if selected:
        skills = ", ".join(selected.get("matched_skills") or []) or "n/a"
        msg = (
            f"Sorted {len(scored)} jobs against CV "
            f"({len(profile.skills)} skills). Top: {selected['title']} @ "
            f"{selected['company']} (score={selected.get('score')}, skills={skills})"
        )
    else:
        msg = "No jobs to sort/select."

    source = (prefs.get("source") or "himalayas").lower()
    snapshot = {
        "wellfound": "output/wellfound_jobs.json",
        "glassdoor": "output/glassdoor_jobs.json",
        "remoteok": "output/remoteok_jobs.json",
        "remotive": "output/remotive_jobs.json",
        "boards": "output/jobs.json",
    }.get(source, "output/himalayas_jobs.json")
    persist_jobs(scored, snapshot)

    return {
        "jobs": scored,
        "sorted_jobs": scored,
        "selected_job": selected,
        "messages": [*state.get("messages", []), msg, f"Wrote ranked jobs to {snapshot}"],
    }
