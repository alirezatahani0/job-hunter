from __future__ import annotations

from collections.abc import Callable

from job_assistant.nodes.apply_job import apply_to_job
from job_assistant.nodes.optimize_cv import tailor_resume
from job_assistant.services.trello import TrelloClient, trello_from_env
from job_assistant.state import Job

TAILORED = "Tailored"
APPLIED = "Applied"
NEEDS_YOU = "Needs you"


def posting_url(card: dict) -> str:
    for line in (card.get("desc") or "").splitlines():
        if line.lower().startswith("url:"):
            return line.split(":", 1)[1].strip()
    return ""


def advance_found_cards(
    jobs: list[Job],
    base_cv: str,
    *,
    client: TrelloClient | None = None,
    tailor: Callable[[Job, str], dict] | None = None,
    apply: Callable[[Job, str], dict] | None = None,
) -> list[str]:
    """Tailor and prepare an application packet for every card in Found."""
    board = client or trello_from_env()
    tailor_fn = tailor or tailor_resume
    apply_fn = apply or _apply_packet
    by_url = {(job.get("url") or "").strip(): job for job in jobs if job.get("url")}
    messages: list[str] = []

    for card in board.cards_in("Found"):
        name = card.get("name") or card.get("id") or "card"
        url = posting_url(card)
        job = by_url.get(url)
        if job is None:
            _needs_you(board, card, f"No saved listing for {url or name}.")
            messages.append(f"Needs you: {name} has no matching job.")
            continue
        try:
            tailored = tailor_fn(job, base_cv)
            cv_text = (tailored.get("updated_cv") or "").strip()
            if not cv_text:
                raise ValueError("Tailor returned an empty resume.")
            board.move_card(card["id"], TAILORED)
            board.add_comment(card["id"], "Tailored the resume for this role.")
        except Exception as exc:  # noqa: BLE001
            _needs_you(board, card, f"Tailor failed: {exc}")
            messages.append(f"Needs you: {name} tailor failed ({exc}).")
            continue
        try:
            packet = apply_fn(job, cv_text)
            for path in (packet.get("resume_path"), packet.get("cover_path")):
                if path:
                    board.attach_file(card["id"], str(path))
            if packet.get("submitted"):
                board.move_card(card["id"], APPLIED)
                board.add_comment(card["id"], packet.get("submit_detail") or "Submitted the employer form.")
                messages.append(f"Applied: {name}.")
                continue
            reason = packet.get("submit_detail") or _unsent_reason(job)
            if packet.get("needs_you"):
                _needs_you(board, card, reason)
                messages.append(f"Needs you: {name}. {reason}")
                continue
            board.add_comment(card["id"], reason)
            messages.append(f"Tailored: {name}. {reason}")
        except Exception as exc:  # noqa: BLE001
            _needs_you(board, card, f"Apply packet failed after tailoring: {exc}")
            messages.append(f"Needs you: {name} apply packet failed ({exc}).")
    return messages


def _unsent_reason(job: Job) -> str:
    source = (job.get("source") or "").strip() or "the job board"
    url = (job.get("url") or "").strip()
    return (
        "Failed at the submit step. The resume and cover letter are ready, "
        f"but the employer form on {source} was not opened or sent. "
        f"Posting: {url}"
    )


def _apply_packet(job: Job, cv_text: str) -> dict:
    return apply_to_job(
        job,
        matched=list(job.get("matched_skills") or []),
        cv_source="optimized",
        cv_text=cv_text,
    )


def _needs_you(board: TrelloClient, card: dict, text: str) -> None:
    board.move_card(card["id"], NEEDS_YOU)
    board.add_comment(card["id"], text)
