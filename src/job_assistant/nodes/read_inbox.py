"""Read new mail and update the board. Newsletters stay put."""

from __future__ import annotations

import json
from pathlib import Path

from job_assistant.services.mail import process_inbox
from job_assistant.services.mailbox import fetch_recent_mail

SEEN_PATH = Path("output") / "seen_mail.json"
_BOARD_LISTS = ("Applied", "Replied", "Interview", "Needs you", "Tailored")


def read_inbox(
    *,
    fetch=None,
    cards=None,
    move=None,
    note=None,
    reply=None,
    seen_path: Path | None = None,
) -> list[str]:
    fetch_fn = fetch or fetch_recent_mail
    try:
        messages = list(fetch_fn())
    except Exception as exc:
        return [f"Mail: could not read the inbox ({exc})."]

    path = Path(seen_path) if seen_path is not None else SEEN_PATH
    seen = _load_seen(path)
    fresh = [message for message in messages if message.message_id not in seen]
    if not fresh:
        return ["Mail: read the inbox. Nothing new to act on."]

    if cards is None or move is None or note is None or reply is None:
        live_cards, live_move, live_note, live_reply = _live_actions()
        cards = live_cards if cards is None else cards
        move = live_move if move is None else move
        note = live_note if note is None else note
        reply = live_reply if reply is None else reply

    lines = process_inbox(fresh, list(cards), reply=reply, move=move, note=note)
    seen.update(message.message_id for message in fresh)
    _save_seen(path, seen)
    return lines or ["Mail: read the inbox. Nothing new to act on."]


def _load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {str(item) for item in payload}
    return set()


def _save_seen(path: Path, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")


def _live_actions():
    from job_assistant.services.trello import trello_from_env

    board = trello_from_env()
    cards = []
    for name in _BOARD_LISTS:
        cards.extend(board.cards_in(name))

    def move(card: dict) -> None:
        board.move_card(card["id"], "Rejected")

    def note(card: dict, text: str) -> None:
        board.add_comment(card["id"], text)

    def reply(message, body: str) -> None:
        _reply_in_mail(message.message_id, body)

    return cards, move, note, reply


def _reply_in_mail(message_id: str, body: str) -> None:
    from job_assistant.services.mailbox import reply_in_mail

    reply_in_mail(message_id, body)
