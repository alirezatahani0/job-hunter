import unittest

from job_assistant.services.more_boards import (
    parse_dailyremote,
    parse_javascript_jobs,
    parse_jobicy,
    parse_reactjobsboard,
    parse_remote_frontend,
)


class MoreBoardTests(unittest.TestCase):
    def test_jobicy_keeps_anywhere_as_worldwide(self):
        jobs = parse_jobicy(
            {
                "jobs": [
                    {
                        "id": 1,
                        "jobTitle": "Senior Frontend Engineer",
                        "companyName": "Northwind",
                        "jobGeo": "Anywhere",
                        "url": "https://jobicy.com/jobs/1",
                        "jobExcerpt": "React and TypeScript.",
                    },
                    {
                        "id": 2,
                        "jobTitle": "Senior Frontend Engineer",
                        "companyName": "Local",
                        "jobGeo": "USA",
                        "url": "https://jobicy.com/jobs/2",
                    },
                ]
            }
        )
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["location"], "Worldwide")
        self.assertEqual(jobs[0]["company"], "Northwind")
        self.assertEqual(jobs[1]["location"], "Remote, USA")

    def test_dailyremote_reads_the_card(self):
        html = """
        <h2 class="lst-card__title">
          <a href="/remote-job/frontend-engineer-10">Frontend Engineer</a>
        </h2>
        <span class="lst-card__locked">Company hidden</span>
        <span class="lst-pill"><span>Worldwide</span></span>
        """
        jobs = parse_dailyremote(html)
        self.assertEqual(jobs[0]["title"].strip(), "Frontend Engineer")
        self.assertEqual(jobs[0]["location"], "Worldwide")
        self.assertTrue(jobs[0]["url"].endswith("/remote-job/frontend-engineer-10"))

    def test_javascript_jobs_reads_company_and_place(self):
        html = """
        <a href="https://javascript.jobs/job/react-frontend-engineer-2">
          <div class="tw-text-lg tw-font-medium">React Frontend Engineer</div>
          <span class="tw-card-title">ThunderSoft</span>
          <span class="tw-location">Poland</span>
        </a>
        """
        jobs = parse_javascript_jobs(html)
        self.assertEqual(jobs[0]["company"], "ThunderSoft")
        self.assertEqual(jobs[0]["title"].strip(), "React Frontend Engineer")
        self.assertEqual(jobs[0]["location"], "Remote, Poland")

    def test_remote_frontend_reads_company_and_worldwide(self):
        html = """
        <a href="/cmvnx-frontend-engineer">
          <h2>Frontend Engineer</h2>
          <p>Fairarena<span><svg></svg>Worldwide</span></p>
        </a>
        """
        jobs = parse_remote_frontend(html)
        self.assertEqual(jobs[0]["company"], "Fairarena")
        self.assertEqual(jobs[0]["location"], "Worldwide")
        self.assertIn("remotefrontendjobs.com", jobs[0]["url"])

    def test_reactjobsboard_reads_the_hiring_line(self):
        html = """
        <a href="/remote-jobs/446426-senior-frontend-engineer-muck-rack">
          <span>Muck Rack<span class="text-sm">is hiring</span></span>
          <span class="text-2xl text-primaryColor font-bold">Senior Frontend Engineer</span>
          <span>Remote —</span><a href="/remote-bulgaria-tech-jobs">Bulgaria</a>
        </a>
        """
        jobs = parse_reactjobsboard(html)
        self.assertEqual(jobs[0]["company"], "Muck Rack")
        self.assertEqual(jobs[0]["title"], "Senior Frontend Engineer")
        self.assertEqual(jobs[0]["location"], "Remote, Bulgaria")
        self.assertTrue(jobs[0]["url"].startswith("https://reactjobsboard.com/"))


if __name__ == "__main__":
    unittest.main()
