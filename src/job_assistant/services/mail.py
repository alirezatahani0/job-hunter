from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MailMessage:
    message_id: str
    sender: str
    subject: str
    body: str


_NEWSLETTER = (
    "unsubscribe",
    "newsletter",
    "job alert",
    "noreply",
    "no-reply",
    "notifications@",
    "digest",
)

_REJECTION = (
    "other candidates",
    "not moving forward",
    "not selected",
    "we regret",
    "unfortunately",
    "unsuccessful",
    "position has been filled",
    "decided to proceed with",
)

_INTERVIEW = (
    "interview",
    "schedule a call",
    "schedule a time",
    "your availability",
    "calendly",
    "book a time",
)


def decide(message: MailMessage) -> str:
    text = f"{message.sender}\n{message.subject}\n{message.body}".lower()
    if any(phrase in text for phrase in _REJECTION):
        return "rejection"
    if any(phrase in text for phrase in _INTERVIEW):
        return "interview"
    if any(phrase in text for phrase in _NEWSLETTER):
        return "newsletter"
    if "?" in message.body or "could you" in text or "can you" in text:
        return "question"
    return "ignore"


def match_card(message: MailMessage, cards: list[dict]) -> dict | None:
    text = f"{message.sender}\n{message.subject}\n{message.body}".lower()
    for card in cards:
        company = _company(card.get("name") or "")
        if len(company) >= 3 and company.lower() in text:
            return card
    return None


def _company(name: str) -> str:
    if "—" in name:
        return name.split("—")[-1].strip()
    return ""


INTERVIEW_REPLY = (
    "Thanks for reaching out. I'm happy to talk. "
    "What times work on your side?"
)


def process_inbox(messages, cards, *, reply, move, note) -> list[str]:
    lines: list[str] = []
    for message in messages:
        kind = decide(message)
        if kind in {"newsletter", "ignore"}:
            lines.append(f"Mail: left alone ({message.subject})")
            continue
        card = match_card(message, cards)
        if kind == "rejection":
            if card is None:
                lines.append(f"Mail: rejection did not match a card ({message.subject})")
                continue
            move(card)
            lines.append(f"Mail: moved to Rejected ({card.get('name')})")
            continue
        if kind == "interview":
            reply(message, INTERVIEW_REPLY)
            if card is not None:
                note(card, "Replied to the interview invite.")
            lines.append(f"Mail: replied ({message.subject})")
            continue
        if card is not None:
            note(card, "An email asked a question. It was not answered automatically.")
        lines.append(f"Mail: question needs you ({message.subject})")
    return lines
