from __future__ import annotations

from datetime import datetime
from pathlib import Path


def board_report(*, fetched: int, kept: int, ranked: int, stats: dict) -> str:
    return (
        f"The run fetched {fetched} and kept {kept}. "
        f"Ranking scored all {ranked}. "
        f"From those, it skipped {stats.get('dropped_existing', 0)} already on the board, "
        f"{stats.get('dropped_checked', 0)} already checked, "
        f"{stats.get('dropped_us', 0)} US-only, "
        f"{stats.get('dropped_region', 0)} country-locked, "
        f"{stats.get('dropped_role', 0)} outside frontend/full-stack, "
        f"{stats.get('dropped_unpaid', 0)} unpaid, "
        f"and {stats.get('dropped_score', 0)} at or below 50%. "
        f"It added {stats.get('chosen', 0)}."
    )


def save_run_report(lines: list[str], directory: str | Path = "output/reports") -> Path:
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    text = "\n".join(line for line in lines if line).strip() + "\n"
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    (folder / f"{stamp}.md").write_text(text, encoding="utf-8")
    latest = folder / "latest.md"
    latest.write_text(text, encoding="utf-8")
    return latest
