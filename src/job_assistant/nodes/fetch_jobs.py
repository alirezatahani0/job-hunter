from __future__ import annotations

import json
from pathlib import Path

from job_assistant.services.glassdoor import GlassdoorBlocked, fetch_glassdoor_jobs
from job_assistant.services.remote import is_remote_job
from job_assistant.services.himalayas import fetch_himalayas_jobs
from job_assistant.services.remoteok import fetch_remoteok_jobs
from job_assistant.services.remotive import fetch_remotive_jobs
from job_assistant.services.wellfound import fetch_wellfound_jobs
from job_assistant.state import Job, JobAssistantState

TECH_CATEGORIES = {
    "software development",
    "devops",
    "data and analytics",
    "information technology",
    "developer",
    "engineering",
}


def _apply_filters(jobs: list[Job], prefs: dict) -> list[Job]:
    location = (prefs.get("location") or "").strip().lower()
    prefer_tech = bool(prefs.get("prefer_tech", True))

    filtered = jobs
    if prefer_tech:
        techish = [
            j
            for j in filtered
            if (j.get("category") or "").lower() in TECH_CATEGORIES
            or (j.get("source") in {"himalayas", "wellfound", "glassdoor"})
            or any(
                token in (j.get("title") or "").lower()
                for token in (
                    "engineer",
                    "developer",
                    "software",
                    "backend",
                    "frontend",
                    "front-end",
                    "full-stack",
                    "fullstack",
                    "devops",
                    "sre",
                    "data scientist",
                    "machine learning",
                )
            )
        ]
        if techish:
            filtered = techish

    if location and location != "remote":
        filtered = [
            j
            for j in filtered
            if location in j["location"].lower()
            or "worldwide" in j["location"].lower()
            or "all countries" in j["location"].lower()
            or "anywhere" in j["location"].lower()
        ]

    if prefs.get("remote_only", True):
        filtered = [j for j in filtered if is_remote_job(j)]

    return filtered


def persist_jobs(jobs: list[Job], path: str | Path) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "count": len(jobs),
        "jobs": jobs,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(out)


def fetch_jobs_node(state: JobAssistantState) -> dict:
    prefs = state.get("preferences") or {}
    max_jobs = int(state.get("max_jobs") or prefs.get("max_jobs") or 40)
    source = (prefs.get("source") or "himalayas").lower()
    query = (prefs.get("query") or "").strip()
    pages = int(prefs.get("himalayas_pages") or prefs.get("wellfound_pages") or 3)

    jobs: list[Job] = []
    notes: list[str] = []
    boards = source == "boards"
    used = source
    snapshot_path = {
        "himalayas": "output/himalayas_jobs.json",
        "wellfound": "output/wellfound_jobs.json",
        "glassdoor": "output/glassdoor_jobs.json",
        "remoteok": "output/remoteok_jobs.json",
        "remotive": "output/remotive_jobs.json",
        "boards": "output/jobs.json",
    }.get(source, "output/jobs.json")

    def _take(name: str, batch: list[Job], *, replace: bool) -> None:
        nonlocal jobs, used
        if replace:
            jobs = batch
            used = name
            return
        seen = {(j["title"].lower(), j["company"].lower()) for j in jobs}
        added = 0
        for job in batch:
            key = (job["title"].lower(), job["company"].lower())
            if key in seen:
                continue
            jobs.append(job)
            seen.add(key)
            added += 1
        if added:
            used = f"{used}+{name}" if used else name

    def _load(name: str, loader) -> None:
        replace = source == name
        try:
            batch = loader()
        except GlassdoorBlocked as exc:
            notes.append(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            if boards or name == "glassdoor":
                notes.append(f"{name} skipped: {exc}")
                return
            raise
        _take(name, batch, replace=replace)

    if source in {"himalayas", "auto", "boards"}:
        queries = [query] if query else []
        extra = prefs.get("himalayas_queries") or [
            "frontend engineer",
            "full stack engineer",
        ]
        if isinstance(extra, str):
            extra = [q.strip() for q in extra.split(",") if q.strip()]
        for item in extra:
            if item not in queries:
                queries.append(item)
        _load(
            "himalayas",
            lambda: fetch_himalayas_jobs(
                queries=queries,
                pages=pages,
                limit=max(max_jobs, 40),
                worldwide_only=bool(prefs.get("worldwide_only", True)),
                relevant_only=True,
            ),
        )

    if source == "wellfound" or boards or (
        source == "auto" and len(_apply_filters(jobs, prefs)) < 5
    ):
        roles = prefs.get("wellfound_roles")
        if isinstance(roles, str):
            roles = [r.strip() for r in roles.split(",") if r.strip()]
        _load(
            "wellfound",
            lambda: fetch_wellfound_jobs(
                roles=roles,
                pages=int(prefs.get("wellfound_pages") or 2),
                remote_only=bool(prefs.get("remote_only", True)),
                limit=max(max_jobs, 40),
                relevant_only=True,
            ),
        )

    if source in {"glassdoor", "boards"}:
        glassdoor_queries = [query] if query else []
        for item in ("frontend engineer", "full stack engineer", "react"):
            if item not in glassdoor_queries:
                glassdoor_queries.append(item)
        _load(
            "glassdoor",
            lambda: fetch_glassdoor_jobs(
                queries=glassdoor_queries,
                limit=max(max_jobs, 40),
                relevant_only=True,
            ),
        )

    if source == "remoteok" or boards or (
        source == "auto" and len(_apply_filters(jobs, prefs)) < 5
    ):
        tags = ["react", "frontend", "typescript"] if boards else None
        _load(
            "remoteok",
            lambda: fetch_remoteok_jobs(tags=tags, limit=max(max_jobs, 80)),
        )

    if source == "remotive" or boards or (
        source == "auto" and len(_apply_filters(jobs, prefs)) < 5
    ):
        search = query or ("frontend" if boards else None)
        _load(
            "remotive",
            lambda: fetch_remotive_jobs(search=search, limit=max(max_jobs, 80)),
        )

    filtered = _apply_filters(jobs, prefs)
    if not boards:
        filtered = filtered[:max_jobs]

    updates: dict = {
        "jobs": filtered,
        "messages": [
            *state.get("messages", []),
            (
                f"Fetched {len(jobs)} jobs via {used}; {len(filtered)} saved to state"
                + (f" (query={query!r})" if query else "")
                + "."
            ),
            *notes,
        ],
    }

    if filtered:
        path = persist_jobs(filtered, snapshot_path)
        updates["messages"].append(f"Wrote job list snapshot to {path}")

    return updates
