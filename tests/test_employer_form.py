import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader

from job_assistant.services.cv_docx import markdown_to_docx
from job_assistant.services.employer_form import (
    classify_apply_url,
    dover_fields,
    dover_job_id,
    himalayas_company_slug,
    pick_location,
    resolve_apply_url,
)
from job_assistant.services.resume_pdf import docx_to_pdf


class FakeResponse:
    def __init__(self, status, url, payload):
        self.status_code = status
        self.url = url
        self._payload = payload

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, link):
        self.link = link
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        if "apply-link" in url:
            return FakeResponse(200, url, {"applicationLink": self.link})
        return FakeResponse(200, "https://app.dover.com/apply/perena/job-id", {})


class EmployerFormTests(unittest.TestCase):
    def test_classify_and_dover_id(self):
        self.assertEqual(
            classify_apply_url("https://app.dover.com/apply/perena/b3c97469-ac37-4106-92c1-5f1b28196ea9"),
            "dover",
        )
        self.assertEqual(
            dover_job_id("https://app.dover.com/apply/perena/b3c97469-ac37-4106-92c1-5f1b28196ea9"),
            "b3c97469-ac37-4106-92c1-5f1b28196ea9",
        )
        self.assertEqual(
            himalayas_company_slug("https://himalayas.app/companies/perena/jobs/frontend-engineer"),
            ("perena", "frontend-engineer"),
        )

    def test_location_prefers_sofia(self):
        options = [
            {"value": "1", "label": "Armenia (Erevan, Erevan, Armenia)"},
            {"value": "233318", "label": "Bulgaria (Sofia, Sofia, Bulgaria)"},
        ]
        chosen = pick_location(options)
        self.assertEqual(chosen["value"], "233318")

    def test_dover_fields_use_the_form_phone_and_linkedin(self):
        fields = dover_fields(job_id="job-1")
        self.assertEqual(fields["first_name"], "Alireza")
        self.assertEqual(fields["email"], "alireza.tahani01@gmail.com")
        self.assertEqual(fields["phone_number"], "+372 5605 7387")
        self.assertIn("/in/", fields["linkedin_url"])

    def test_resolve_follows_the_himalayas_apply_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "links.json"
            with patch("job_assistant.services.employer_form.APPLY_LINKS_PATH", path):
                final = resolve_apply_url(
                    "https://himalayas.app/companies/perena/jobs/frontend-engineer",
                    FakeClient("https://himalayas.app/apply/pnhwn"),
                )
        self.assertEqual(final, "https://app.dover.com/apply/perena/job-id")

    def test_signed_out_himalayas_has_no_apply_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "links.json"
            with patch("job_assistant.services.employer_form.APPLY_LINKS_PATH", path):
                final = resolve_apply_url(
                    "https://himalayas.app/companies/perena/jobs/frontend-engineer",
                    FakeClient(None),
                )
        self.assertIsNone(final)

    def test_resume_pdf_keeps_the_name_and_drops_the_phone(self):
        docx = markdown_to_docx("# Alireza Tahani\n\nEmail: alireza.tahani01@gmail.com\n\nBuilds React.")
        pdf = docx_to_pdf(docx)
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("Alireza Tahani", text)
        self.assertNotIn("5605", text)
        self.assertNotIn("+372", text)


if __name__ == "__main__":
    unittest.main()
