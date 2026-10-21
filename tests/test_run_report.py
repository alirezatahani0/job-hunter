import unittest
from unittest.mock import patch

from job_assistant.nodes.sort_jobs import sort_jobs_node
from job_assistant.services.run_report import board_report


def listing(index: int) -> dict:
    return {
        "id": str(index),
        "title": "Frontend Engineer",
        "company": f"Company {index}",
        "location": "Remote",
        "tags": ["react"],
        "salary_min": None,
        "salary_max": None,
        "salary_text": "",
        "url": f"https://example.com/{index}",
        "description": "React and TypeScript for a worldwide remote team.",
    }


class SortKeepTests(unittest.TestCase):
    def test_boards_ranking_keeps_every_fetched_job(self):
        state = {
            "preferences": {"source": "boards", "max_jobs": 1},
            "max_jobs": 1,
            "jobs": [listing(1), listing(2), listing(3)],
            "base_cv": "React TypeScript",
            "messages": [],
        }
        with patch("job_assistant.nodes.sort_jobs.persist_jobs", return_value="output/jobs.json"):
            result = sort_jobs_node(state)
        self.assertEqual(len(result["sorted_jobs"]), 3)


class BoardReportTests(unittest.TestCase):
    def test_report_names_every_skip(self):
        text = board_report(
            fetched=97,
            kept=86,
            ranked=86,
            stats={
                "dropped_existing": 4,
                "dropped_us": 11,
                "dropped_region": 13,
                "dropped_role": 3,
                "dropped_score": 20,
                "chosen": 8,
            },
        )
        self.assertIn("fetched 97", text)
        self.assertIn("kept 86", text)
        self.assertIn("scored all 86", text)
        self.assertIn("4 already on the board", text)
        self.assertIn("11 US-only", text)
        self.assertIn("13 country-locked", text)
        self.assertIn("3 outside frontend/full-stack", text)
        self.assertIn("20 at or below 50%", text)
        self.assertIn("added 8", text)


if __name__ == "__main__":
    unittest.main()
