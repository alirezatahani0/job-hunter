from __future__ import annotations

import re

from job_assistant.services.eligibility import card_description, card_name, choose_board_jobs
from job_assistant.services.run_report import board_report
from job_assistant.services.trello import TrelloClient, trello_from_env, urls_on_card
from job_assistant.state import JobAssistantState

FOUND = "Found"


def publish_board_node(state: JobAssistantState, client: TrelloClient | None = None) -> dict:
    """Add the best new matches to the Found column. Skip cards already on the board."""
    jobs = list(state.get("sorted_jobs") or state.get("jobs") or [])
    board = client or trello_from_env()
    existing: set[str] = set()
    for card in board.open_cards():
        existing.update(urls_on_card(card))

    chosen, stats = choose_board_jobs(jobs, existing)
    links: list[str] = []
    for job in chosen:
        created = board.create_card(
            list_name=FOUND,
            name=card_name(job),
            desc=card_description(job),
            url=(job.get("url") or "").strip(),
        )
        link = created.get("shortUrl") or created.get("url") or job.get("url") or ""
        if link:
            links.append(str(link))

    summary = (
        f"Trello Found: added {stats['chosen']} "
        f"(skipped {stats['dropped_existing']} already on the board, "
        f"{stats['dropped_us']} US-only, {stats['dropped_region']} country-locked, "
        f"{stats['dropped_remote']} not remote, "
        f"{stats['dropped_role']} outside frontend/full-stack, "
        f"{stats['dropped_score']} at or below 50%)."
    )
    if links:
        summary = summary + " " + " ".join(links)
    prior = list(state.get("messages") or [])
    report = board_report(
        fetched=_first_int(prior, r"Fetched (\d+) jobs"),
        kept=_first_int(prior, r"; (\d+) saved"),
        ranked=_first_int(prior, r"Sorted (\d+) jobs"),
        stats=stats,
    )
    return {"messages": [*prior, summary, report]}


def _first_int(messages: list[str], pattern: str) -> int:
    for message in messages:
        match = re.search(pattern, message)
        if match:
            return int(match.group(1))
    return 0
