from __future__ import annotations

from collections.abc import Callable


def run_daily(
    *,
    fetch: Callable[[], list[str]],
    advance: Callable[[], list[str]],
    submit: Callable[[], list[str]],
    inbox: Callable[[], list[str]],
) -> list[str]:
    messages: list[str] = []
    for name, step in (
        ("fetch", fetch),
        ("advance", advance),
        ("submit", submit),
        ("inbox", inbox),
    ):
        try:
            messages.extend(step() or [])
        except Exception as exc:
            messages.append(f"{name} failed: {exc}")
    return messages
