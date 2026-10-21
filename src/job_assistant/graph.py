from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from job_assistant.nodes.apply_job import apply_job_node
from job_assistant.nodes.evaluate_cv import evaluate_cv_node
from job_assistant.nodes.fetch_jobs import fetch_jobs_node
from job_assistant.nodes.optimize_cv import optimize_cv_node
from job_assistant.nodes.print_output import print_output_node
from job_assistant.nodes.publish_board import publish_board_node
from job_assistant.nodes.sort_jobs import sort_jobs_node
from job_assistant.nodes.write_cover_letter import write_cover_letter_node
from job_assistant.state import JobAssistantState


def build_graph(*, fetch_only: bool = False, until: str | None = None):
    """Build and compile the job assistant workflow.

    Full flow:
      fetch_jobs -> sort_jobs -> optimize_cv -> evaluate_cv
      -> write_cover_letter -> apply_job -> print_output

    until:
      fetch — stop after fetching
      sort  — fetch then rank against the CV
      board — fetch, rank, then add the top new matches to Trello Found
      optimize — fetch, rank, then tailor a human/ATS-safe CV for the top job
      cover — through Claude cover letter (no apply open)
      apply — through apply packet (cover letter + apply URL)
      end   — full pipeline
    """
    if until is None:
        until = "fetch" if fetch_only else "end"

    graph = StateGraph(JobAssistantState)
    graph.add_node("fetch_jobs", fetch_jobs_node)
    graph.add_edge(START, "fetch_jobs")

    if until == "fetch":
        graph.add_edge("fetch_jobs", END)
        return graph.compile()

    graph.add_node("sort_jobs", sort_jobs_node)
    graph.add_edge("fetch_jobs", "sort_jobs")
    if until == "sort":
        graph.add_edge("sort_jobs", END)
        return graph.compile()

    if until == "board":
        graph.add_node("publish_board", publish_board_node)
        graph.add_edge("sort_jobs", "publish_board")
        graph.add_edge("publish_board", END)
        return graph.compile()

    graph.add_node("optimize_cv", optimize_cv_node)
    graph.add_edge("sort_jobs", "optimize_cv")
    if until == "optimize":
        graph.add_edge("optimize_cv", END)
        return graph.compile()

    graph.add_node("evaluate_cv", evaluate_cv_node)
    graph.add_edge("optimize_cv", "evaluate_cv")
    graph.add_node("write_cover_letter", write_cover_letter_node)
    graph.add_edge("evaluate_cv", "write_cover_letter")
    if until == "cover":
        graph.add_edge("write_cover_letter", END)
        return graph.compile()

    graph.add_node("apply_job", apply_job_node)
    graph.add_edge("write_cover_letter", "apply_job")
    if until == "apply":
        graph.add_edge("apply_job", END)
        return graph.compile()

    graph.add_node("print_output", print_output_node)
    graph.add_edge("apply_job", "print_output")
    graph.add_edge("print_output", END)
    return graph.compile()
