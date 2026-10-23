import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from job_assistant.nodes.optimize_cv import tailor_resume
from job_assistant.nodes.write_cover_letter import write_cover_letter_for_job
from job_assistant.services.local_draft import draft_cover, draft_resume

CV = """# Alireza Tahani

**Email:** alireza.tahani01@gmail.com

## Professional Summary

Senior full-stack engineer (9+ years) shipping TypeScript, React, and Node.js.

## Core Competencies

- TypeScript, JavaScript, React, Next.js, Node.js, Express

## Experience

### Lead FrontEnd Developer — SAP (Germany) / Identity Global (UK) | May 2023 – Present

- Led 3 front-end engineers on a trading platform.
- Built spot and futures interfaces with 200ms live market data refresh.
"""


class LocalDraftTests(unittest.TestCase):
    def test_resume_keeps_real_work_and_skips_skills_the_cv_lacks(self):
        job = {
            "title": "Senior Full-Stack Engineer (NestJS, PostgreSQL)",
            "company": "Example",
            "description": "Need NestJS, Prisma, PostgreSQL, and React.",
            "matched_skills": ["React", "Node.js", "NestJS"],
        }
        updated, _changes, lead = draft_resume(CV, job, job["matched_skills"])
        self.assertIn("Identity Global", updated)
        self.assertIn("React", updated)
        self.assertIn("Node.js", updated)
        self.assertNotIn("NestJS", updated)
        self.assertNotIn("PostgreSQL", updated)
        self.assertNotIn("Prisma", updated)
        self.assertNotIn("NestJS", " ".join(lead))
        self.assertIn("this role", updated)

    def test_cover_names_the_company_and_leaves_out_the_phone(self):
        letter, points = draft_cover(
            CV,
            {"title": "Senior Frontend Engineer", "company": "Northwind"},
            ["React", "TypeScript"],
        )
        self.assertIn("Northwind", letter)
        self.assertIn("Senior Frontend Engineer", letter)
        self.assertIn("alireza.tahani01@gmail.com", letter)
        self.assertNotIn("5605", letter)
        self.assertNotIn("+372", letter)
        self.assertTrue(points)

    def test_tailor_and_letter_do_not_call_an_outside_model(self):
        job = {
            "id": "job-9",
            "title": "Senior Frontend Engineer",
            "company": "Northwind",
            "url": "https://example.com/jobs/1",
            "description": "React and TypeScript.",
            "tags": ["React"],
            "matched_skills": ["React", "TypeScript"],
        }

        def fail(*_args, **_kwargs):
            raise AssertionError("outside model was called")

        with (
            patch("job_assistant.services.llm.get_llm", fail),
            patch("job_assistant.nodes.optimize_cv._persist") as persist,
            tempfile.TemporaryDirectory() as tmp,
        ):
            persist.side_effect = lambda _job, updated, changes, keywords: {
                "cv": updated,
                "md": "memory",
                "json": "memory",
            }
            tailored = tailor_resume(job, CV)
            self.assertIn("React", tailored["updated_cv"])
            self.assertNotIn("5605", tailored["updated_cv"])

            from job_assistant.nodes import write_cover_letter as letters

            original = letters.COVER_LETTERS_PATH
            letters.COVER_LETTERS_PATH = Path(tmp) / "cover_letters.json"
            try:
                saved = write_cover_letter_for_job(job, cv_text=tailored["updated_cv"])
            finally:
                letters.COVER_LETTERS_PATH = original
            self.assertIn("Northwind", saved["cover_letter"])
            self.assertTrue(str(saved["cover_path"]).endswith(".docx"))


if __name__ == "__main__":
    unittest.main()
