from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from job_assistant.state import JobAssistantState


def print_output_node(state: JobAssistantState) -> dict:
    job = state.get("selected_job")
    updated_cv = state.get("updated_cv") or ""
    evaluation = state.get("evaluation")

    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_company = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in ((job or {}).get("company") or "unknown")
    )[:40]
    out_path = out_dir / f"application_{safe_company}_{stamp}.md"

    lines: list[str] = [
        "# Job Assistant Output",
        "",
        "## Job Description Link",
    ]
    if job:
        lines.extend(
            [
                f"- **Title:** {job.get('title')}",
                f"- **Company:** {job.get('company')}",
                f"- **Location:** {job.get('location')}",
                f"- **Salary:** {job.get('salary_text') or 'not listed'}",
                f"- **Match score:** {job.get('score', 'n/a')}",
                f"- **URL:** {job.get('url') or 'n/a'}",
                "",
            ]
        )
    else:
        lines.extend(["No job selected.", ""])

    if evaluation:
        lines.extend(
            [
                "## CV Evaluation",
                f"- JD relevance: {evaluation['jd_relevance']:.1f}/100",
                f"- Human readability: {evaluation['human_readability']:.1f}/100",
                f"- Format quality: {evaluation['format_quality']:.1f}/100",
                f"- ATS score: {evaluation['ats_score']:.1f}/100",
                f"- ATS pass: {'PASS' if evaluation['ats_pass'] else 'FAIL'}",
                f"- AI-written flag: {'YES' if evaluation['ai_detected'] else 'NO'}",
                f"- Overall: {evaluation['overall']:.1f}/100",
                "",
                "### Feedback",
            ]
        )
        for note in evaluation.get("feedback") or []:
            lines.append(f"- {note}")
        lines.append("")

    lines.extend(["## Updated Resume", "", updated_cv.strip(), ""])
    content = "\n".join(lines)
    out_path.write_text(content, encoding="utf-8")

    # Also print a concise console summary for the LangGraph run.
    print("\n" + "=" * 72)
    print("JOB ASSISTANT RESULT")
    print("=" * 72)
    if job:
        print(f"JD URL : {job.get('url')}")
        print(f"Role   : {job.get('title')} @ {job.get('company')}")
    if evaluation:
        print(
            f"Scores : overall={evaluation['overall']:.1f} "
            f"ATS={'PASS' if evaluation['ats_pass'] else 'FAIL'} "
            f"AI_flag={'yes' if evaluation['ai_detected'] else 'no'}"
        )
    print(f"Saved  : {out_path}")
    print("=" * 72 + "\n")
    print(updated_cv[:2000])
    if len(updated_cv) > 2000:
        print("\n... (truncated; see full file) ...\n")

    return {
        "output_path": str(out_path),
        "messages": [*state.get("messages", []), f"Wrote output to {out_path}"],
    }
