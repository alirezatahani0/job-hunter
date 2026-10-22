from __future__ import annotations

_REMOTE = ("remote", "worldwide", "all countries", "anywhere", "work from home", "wfh")
_BLOCKED = (
    "hybrid",
    "on-site",
    "onsite",
    "on site",
    "in-office",
    "in office",
    "partially remote",
    "remote-friendly",
    "remote friendly",
)


def is_remote_job(job: dict) -> bool:
    """True only for fully remote listings. Hybrid and on-site roles are excluded."""
    blob = " ".join(
        [
            str(job.get("location") or ""),
            str(job.get("location_requirements") or ""),
            str(job.get("title") or ""),
            " ".join(str(tag) for tag in (job.get("tags") or [])),
        ]
    ).lower()
    if any(token in blob for token in _BLOCKED):
        return False
    return any(token in blob for token in _REMOTE)
