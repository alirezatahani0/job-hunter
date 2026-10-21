from __future__ import annotations

from job_assistant.nodes.advance_board import posting_url
from job_assistant.nodes.apply_job import load_applications, record_application
from job_assistant.services.browser_apply import submit_application
from job_assistant.services.trello import TrelloClient, trello_from_env

TAILORED = "Tailored"
APPLIED = "Applied"
NEEDS_YOU = "Needs you"


def submit_tailored_cards(client: TrelloClient | None = None, submit=None) -> list[str]:
    """Send the employer form for each Tailored card. Applied only after the form is accepted."""
    board = client or trello_from_env()
    submit_fn = submit or submit_application
    messages: list[str] = []
    for card in board.cards_in(TAILORED):
        name = card.get("name") or card.get("id") or "card"
        url = posting_url(card)
        packet = _packet_for(url)
        if packet and packet.get("submitted"):
            board.move_card(card["id"], APPLIED)
            messages.append(f"Applied: {name} was already submitted.")
            continue
        resume_path = (packet or {}).get("resume_path") or ""
        cover_path = (packet or {}).get("cover_path") or ""
        if not resume_path:
            _needs_you(board, card, "Resume file is missing, so the form was not sent.")
            messages.append(f"Needs you: {name} has no resume file.")
            continue
        outcome = submit_fn(url, resume_path=resume_path, cover_path=cover_path or None)
        if packet:
            record_application(
                {
                    **packet,
                    "submitted": bool(outcome.get("submitted")),
                    "status": "submitted" if outcome.get("submitted") else packet.get("status") or "ready",
                    "submit_detail": outcome.get("detail") or "",
                    "needs_you": bool(outcome.get("needs_you")),
                    "apply_url": outcome.get("apply_url") or packet.get("apply_url") or url,
                }
            )
        detail = outcome.get("detail") or "The employer form was not sent."
        if outcome.get("submitted"):
            board.move_card(card["id"], APPLIED)
            board.add_comment(card["id"], detail)
            messages.append(f"Applied: {name}. {detail}")
            continue
        if outcome.get("needs_you"):
            _needs_you(board, card, detail)
            messages.append(f"Needs you: {name}. {detail}")
            continue
        board.add_comment(card["id"], detail)
        messages.append(f"Tailored: {name}. {detail}")
    return messages


def _packet_for(url: str) -> dict | None:
    if not url:
        return None
    return next((item for item in load_applications() if item.get("url") == url), None)


def _needs_you(board: TrelloClient, card: dict, text: str) -> None:
    board.move_card(card["id"], NEEDS_YOU)
    board.add_comment(card["id"], text)
