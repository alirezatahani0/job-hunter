from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from job_assistant.nodes.evaluate_cv import evaluate_cv_node
from job_assistant.nodes.fetch_jobs import fetch_jobs_node
from job_assistant.nodes.optimize_cv import optimize_cv_node
from job_assistant.nodes.print_output import print_output_node
from job_assistant.nodes.sort_jobs import sort_jobs_node
from job_assistant.state import JobAssistantState


def build_graph(*, fetch_only: bool = False):
    """Build and compile the job assistant workflow.

    Full flow:
      fetch_jobs -> sort_jobs -> optimize_cv -> evaluate_cv -> print_output

    fetch_only:
      fetch_jobs -> END  (jobs remain in state / output/himalayas_jobs.json)
    """
    graph = StateGraph(JobAssistantState)

    graph.add_node("fetch_jobs", fetch_jobs_node)
    graph.add_edge(START, "fetch_jobs")

    if fetch_only:
        graph.add_edge("fetch_jobs", END)
        return graph.compile()

    graph.add_node("sort_jobs", sort_jobs_node)
    graph.add_node("optimize_cv", optimize_cv_node)
    graph.add_node("evaluate_cv", evaluate_cv_node)
    graph.add_node("print_output", print_output_node)

    graph.add_edge("fetch_jobs", "sort_jobs")
    graph.add_edge("sort_jobs", "optimize_cv")
    graph.add_edge("optimize_cv", "evaluate_cv")
    graph.add_edge("evaluate_cv", "print_output")
    graph.add_edge("print_output", END)

    return graph.compile()
