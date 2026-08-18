from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from job_assistant.graph import build_graph
from job_assistant.services.cv_loader import load_cv

console = Console()

DEFAULT_CV = "data/alireza_tahani_cv.md"
DEFAULT_TITLES = (
    "Senior Frontend Engineer,"
    "Lead Frontend Engineer,"
    "Frontend Engineer,"
    "Senior Full-Stack Engineer,"
    "Full-Stack Engineer,"
    "React Developer,"
    "Next.js Developer"
)
DEFAULT_TAGS = "react,typescript,nextjs,javascript,frontend,nodejs"
DEFAULT_QUERY = "react"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the LangGraph job assistant workflow."
    )
    parser.add_argument(
        "--cv",
        default=os.getenv("CV_PATH", DEFAULT_CV),
        help="Path to base CV (markdown/text/pdf)",
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Keyword boost for ranking (default: react)",
    )
    parser.add_argument(
        "--titles",
        default=DEFAULT_TITLES,
        help="Comma-separated preferred job titles",
    )
    parser.add_argument("--location", default="Remote", help="Preferred location substring")
    parser.add_argument(
        "--tags",
        default=DEFAULT_TAGS,
        help="Comma-separated skill/tag ranking signals",
    )
    parser.add_argument("--min-salary", type=int, default=0, help="Minimum salary preference")
    parser.add_argument("--max-jobs", type=int, default=40, help="Max jobs to consider")
    parser.add_argument(
        "--source",
        choices=["himalayas", "wellfound", "auto", "remoteok", "remotive"],
        default="himalayas",
        help="Job source (default: himalayas)",
    )
    parser.add_argument(
        "--himalayas-pages",
        type=int,
        default=3,
        help="How many Himalayas search pages to pull per query",
    )
    parser.add_argument(
        "--wellfound-pages",
        type=int,
        default=2,
        help="How many Wellfound result pages to pull per role",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only fetch jobs into state (skip sort/optimize/evaluate)",
    )
    parser.add_argument(
        "--until",
        choices=["fetch", "sort", "end"],
        default="",
        help="Stop after this node (default: end, or fetch when --fetch-only)",
    )
    parser.add_argument(
        "--prefs-json",
        default="",
        help="Optional JSON file/object overriding preference fields",
    )
    return parser.parse_args()


def load_preferences(args: argparse.Namespace) -> dict:
    titles = [t.strip() for t in args.titles.split(",") if t.strip()]
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    prefs = {
        "query": args.query,
        "titles": titles,
        "location": args.location,
        "tags": tags,
        "min_salary": args.min_salary or None,
        "max_jobs": args.max_jobs,
        "source": args.source,
        "himalayas_pages": args.himalayas_pages,
        "wellfound_pages": args.wellfound_pages,
        "remote_only": True,
        "worldwide_only": True,
    }
    if args.prefs_json:
        raw = args.prefs_json
        if Path(raw).exists():
            data = json.loads(Path(raw).read_text(encoding="utf-8"))
        else:
            data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("--prefs-json must be a JSON object")
        prefs.update(data)
    return prefs


def _print_jobs_table(jobs: list[dict]) -> None:
    table = Table(title=f"Jobs in state ({len(jobs)})")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("Match", justify="right")
    table.add_column("Skills")
    table.add_column("Salary")
    table.add_column("URL", overflow="fold")
    for i, job in enumerate(jobs, start=1):
        score = job.get("score")
        score_text = f"{score * 100:.0f}%" if isinstance(score, (int, float)) else "—"
        skills = ", ".join((job.get("matched_skills") or [])[:4]) or "—"
        table.add_row(
            str(i),
            job.get("title") or "",
            job.get("company") or "",
            score_text,
            skills,
            job.get("salary_text") or "—",
            job.get("url") or "",
        )
    console.print(table)


def main() -> int:
    load_dotenv()
    args = parse_args()
    cv_path = Path(args.cv)
    if not cv_path.exists():
        console.print(f"[red]CV file not found:[/red] {cv_path}")
        return 1

    try:
        base_cv = load_cv(cv_path)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to load CV:[/red] {exc}")
        return 1

    if not base_cv.strip():
        console.print(f"[red]CV is empty after loading:[/red] {cv_path}")
        return 1

    preferences = load_preferences(args)

    until = args.until or ("fetch" if args.fetch_only else "end")
    flow = {
        "fetch": "Himalayas fetch → state",
        "sort": "fetch → sort against CV skills",
        "end": "fetch → sort → optimize CV → evaluate → print",
    }.get(until, until)
    console.print(Panel.fit(flow, title="Job Assistant Graph"))
    console.print(f"CV: {cv_path} ({len(base_cv)} chars)")
    console.print(f"Preferences: {preferences}")

    app = build_graph(until=until)
    result = app.invoke(
        {
            "preferences": preferences,
            "base_cv": base_cv,
            "max_jobs": int(preferences.get("max_jobs") or args.max_jobs),
            "jobs": [],
            "sorted_jobs": [],
            "selected_job": None,
            "updated_cv": "",
            "evaluation": None,
            "output_path": "",
            "messages": [],
        }
    )

    console.print("\n[bold]Node log[/bold]")
    for message in result.get("messages") or []:
        console.print(f"• {message}")

    jobs = result.get("sorted_jobs") or result.get("jobs") or []
    if until in {"fetch", "sort"}:
        _print_jobs_table(jobs)
        label = "ranked" if until == "sort" else "saved"
        console.print(
            f"\n[green]{len(jobs)} jobs {label} in graph state[/green] "
            f"(and output/himalayas_jobs.json)."
        )
        return 0

    if result.get("output_path"):
        console.print(f"\n[green]Done.[/green] Open {result['output_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
