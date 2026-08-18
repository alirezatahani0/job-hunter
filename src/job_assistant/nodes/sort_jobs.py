from __future__ import annotations

from job_assistant.state import Job, JobAssistantState


def _title_score(title: str, preferred_titles: list[str]) -> float:
    if not preferred_titles:
        return 0.5
    title_l = title.lower()
    best = 0.0
    for pref in preferred_titles:
        pref_l = pref.lower().strip()
        if not pref_l:
            continue
        if pref_l == title_l:
            best = max(best, 1.0)
        elif pref_l in title_l or title_l in pref_l:
            best = max(best, 0.85)
        else:
            overlap = len(set(pref_l.split()) & set(title_l.split()))
            if overlap:
                best = max(best, min(0.7, overlap * 0.25))
    return best


def _location_score(location: str, preferred_location: str) -> float:
    if not preferred_location:
        return 0.5
    loc = location.lower()
    pref = preferred_location.lower()
    if pref in loc:
        return 1.0
    if "worldwide" in loc or loc.strip() in {"", "remote"}:
        return 0.75
    return 0.2


def _salary_score(job: Job, min_salary: int | None) -> float:
    high = job.get("salary_max") or job.get("salary_min")
    low = job.get("salary_min")
    if high is None and low is None:
        return 0.35  # unknown salary — mild penalty
    reference = high or low or 0
    if min_salary is None:
        # Normalize roughly into 0–1 around common remote ranges
        return min(1.0, reference / 200_000)
    if reference >= min_salary:
        return min(1.0, 0.7 + (reference - min_salary) / max(min_salary, 1) * 0.3)
    return max(0.0, reference / min_salary * 0.6)


def _tags_score(tags: list[str], preferred_tags: list[str]) -> float:
    if not preferred_tags:
        return 0.5
    tagset = {t.lower() for t in tags}
    hits = sum(1 for t in preferred_tags if t.lower() in tagset)
    return hits / len(preferred_tags)


def score_job(job: Job, preferences: dict) -> float:
    titles = preferences.get("titles") or []
    if isinstance(titles, str):
        titles = [titles]
    tags = preferences.get("tags") or preferences.get("keywords") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    min_salary = preferences.get("min_salary")
    if min_salary is not None:
        min_salary = int(min_salary)

    query = (preferences.get("query") or "").strip().lower()
    query_hit = 0.5
    if query:
        blob = " ".join(
            [
                job.get("title") or "",
                " ".join(job.get("tags") or []),
                (job.get("description") or "")[:1500],
            ]
        ).lower()
        query_hit = 1.0 if query in blob else 0.15

    weights = {
        "title": float(preferences.get("weight_title", 0.30)),
        "salary": float(preferences.get("weight_salary", 0.25)),
        "location": float(preferences.get("weight_location", 0.10)),
        "tags": float(preferences.get("weight_tags", 0.20)),
        "query": float(preferences.get("weight_query", 0.15)),
    }
    total_w = sum(weights.values()) or 1.0

    parts = {
        "title": _title_score(job["title"], titles),
        "salary": _salary_score(job, min_salary),
        "location": _location_score(job["location"], preferences.get("location", "")),
        "tags": _tags_score(job["tags"], tags),
        "query": query_hit,
    }
    return sum(parts[k] * weights[k] for k in parts) / total_w


def sort_jobs_node(state: JobAssistantState) -> dict:
    prefs = state.get("preferences") or {}
    jobs = list(state.get("jobs") or [])

    scored: list[Job] = []
    for job in jobs:
        item = dict(job)
        item["score"] = round(score_job(job, prefs), 4)
        scored.append(item)  # type: ignore[arg-type]

    scored.sort(
        key=lambda j: (
            j.get("score") or 0,
            j.get("salary_max") or j.get("salary_min") or 0,
        ),
        reverse=True,
    )

    selected = scored[0] if scored else None
    msg = (
        f"Sorted {len(scored)} jobs; selected top job: "
        f"{selected['title']} @ {selected['company']} (score={selected.get('score')})"
        if selected
        else "No jobs to sort/select."
    )
    return {
        "sorted_jobs": scored,
        "selected_job": selected,
        "messages": [*state.get("messages", []), msg],
    }
