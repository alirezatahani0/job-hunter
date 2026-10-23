import unittest

from job_assistant.services.checked_jobs import checked_urls_in, load_checked_urls


class CheckedJobsTests(unittest.TestCase):
    def test_reads_urls_from_the_checked_list(self):
        text = """
# Jobs already checked

## Location

- https://example.com/poland — Poland
- https://example.com/spain/ — Spain

A note without a link.
"""
        self.assertEqual(
            checked_urls_in(text),
            {"https://example.com/poland", "https://example.com/spain"},
        )

    def test_the_saved_list_covers_the_jobs_taken_off_the_board(self):
        urls = load_checked_urls()
        self.assertIn(
            "https://bulldogjob.com/companies/jobs/256874-senior-frontend-engineer-truv",
            urls,
        )
        self.assertIn(
            "https://himalayas.app/companies/powerprozesse/jobs/fullstack-developer-100-remote-5284154856",
            urls,
        )
        self.assertIn("https://weworkremotely.com/remote-jobs/toggl-senior-full-stack", urls)
        self.assertGreaterEqual(len(urls), 30)


if __name__ == "__main__":
    unittest.main()
