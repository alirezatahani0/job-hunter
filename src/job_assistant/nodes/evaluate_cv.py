from __future__ import annotations

from job_assistant.services.ats_check import evaluate_ats
from job_assistant.state import JobAssistantState


def evaluate_cv_node(state: JobAssistantState) -> dict:
    job = state.get("selected_job")
    updated_cv = (state.get("updated_cv") or state.get("base_cv") or "").strip()
    if not job or not updated_cv:
        return {
            "evaluation": None,
            "messages": [*state.get("messages", []), "Skipped evaluate: missing job or CV."],
        }

    evaluation = evaluate_ats(updated_cv, job)
    extra = evaluation.get("missing_skills") or []
    msg = (
        f"ATS={'PASS' if evaluation['ats_pass'] else 'FAIL'} "
        f"score={evaluation['ats_score']:.0f} "
        f"AI_flag={'yes' if evaluation['ai_detected'] else 'no'}"
        + (f" missing={', '.join(extra[:5])}" if extra else "")
    )
    return {
        "evaluation": evaluation,
        "messages": [*state.get("messages", []), msg],
    }
