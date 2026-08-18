from __future__ import annotations

import json
from pathlib import Path

from job_assistant.state import Job, JobAssistantState
from job_assistant.services.himalayas import fetch_himalayas_jobs
from job_assistant.services.remoteok import fetch_remoteok_jobs
from job_assistant.services.remotive import fetch_remotive_jobs
from job_assistant.services.wellfound import fetch_wellfound_jobs

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
            or (j.get("source") in {"himalayas", "wellfound"})
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

    if location:
        filtered = [
            j
            for j in filtered
            if location in j["location"].lower()
            or "worldwide" in j["location"].lower()
            or "all countries" in j["location"].lower()
            or "anywhere" in j["location"].lower()
            or (location == "remote" and "remote" in j["location"].lower())
        ]

    return filtered


def _persist_jobs(jobs: list[Job], path: str | Path) -> str:
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
    used = source
    snapshot_path = "output/jobs.json"

    if source in {"himalayas", "auto"}:
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
        jobs = fetch_himalayas_jobs(
            queries=queries,
            pages=pages,
            limit=max(max_jobs, 40),
            worldwide_only=bool(prefs.get("worldwide_only", True)),
            relevant_only=True,
        )
        used = "himalayas"
        snapshot_path = "output/himalayas_jobs.json"

    if source == "wellfound" or (
        source == "auto" and len(_apply_filters(jobs, prefs)) < 5
    ):
        roles = prefs.get("wellfound_roles")
        if isinstance(roles, str):
            roles = [r.strip() for r in roles.split(",") if r.strip()]
        wellfound = fetch_wellfound_jobs(
            roles=roles,
            pages=int(prefs.get("wellfound_pages") or 2),
            remote_only=bool(prefs.get("remote_only", True)),
            limit=max(max_jobs, 40),
            relevant_only=True,
        )
        if source == "wellfound":
            jobs = wellfound
            used = "wellfound"
            snapshot_path = "output/wellfound_jobs.json"
        else:
            seen = {(j["title"].lower(), j["company"].lower()) for j in jobs}
            for job in wellfound:
                key = (job["title"].lower(), job["company"].lower())
                if key not in seen:
                    jobs.append(job)
                    seen.add(key)
            used = f"{used}+wellfound"

    if source == "remoteok" or (
        source == "auto" and len(_apply_filters(jobs, prefs)) < 5
    ):
        remoteok = fetch_remoteok_jobs(tags=None, limit=max(max_jobs, 100))
        if source == "remoteok":
            jobs = remoteok
            used = "remoteok"
        else:
            seen = {(j["title"].lower(), j["company"].lower()) for j in jobs}
            for job in remoteok:
                key = (job["title"].lower(), job["company"].lower())
                if key not in seen:
                    jobs.append(job)
                    seen.add(key)
            used = f"{used}+remoteok"

    if source == "remotive" or (
        source == "auto" and len(_apply_filters(jobs, prefs)) < 5
    ):
        remotive = fetch_remotive_jobs(search=None, limit=max(max_jobs, 100))
        if source == "remotive":
            jobs = remotive
            used = "remotive"
        else:
            seen = {(j["title"].lower(), j["company"].lower()) for j in jobs}
            for job in remotive:
                key = (job["title"].lower(), job["company"].lower())
                if key not in seen:
                    jobs.append(job)
                    seen.add(key)
            used = f"{used}+remotive"

    filtered = _apply_filters(jobs, prefs)[:max_jobs]

    updates: dict = {
        "jobs": filtered,
        "messages": [
            *state.get("messages", []),
            (
                f"Fetched {len(jobs)} jobs via {used}; {len(filtered)} saved to state"
                + (f" (query={query!r})" if query else "")
                + "."
            ),
        ],
    }

    if filtered:
        path = _persist_jobs(filtered, snapshot_path)
        updates["messages"].append(f"Wrote job list snapshot to {path}")

    return updates
