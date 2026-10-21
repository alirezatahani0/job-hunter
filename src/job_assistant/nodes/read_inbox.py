from __future__ import annotations

import os

_GMAIL_KEYS = ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")

NOT_SIGNED_IN = (
    "Mail: Gmail is not signed in for the scheduled job, so the inbox was not read."
)


def gmail_configured() -> bool:
    return all(os.environ.get(name, "").strip() for name in _GMAIL_KEYS)


def read_inbox() -> list[str]:
    if gmail_configured():
        return [
            "Mail: Gmail credentials are set, but the scheduled reader is not connected yet."
        ]
    return [NOT_SIGNED_IN]
