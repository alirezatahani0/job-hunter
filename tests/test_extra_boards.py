import json
import unittest
from html import escape

from job_assistant.services.eastern_boards import (
    parse_bulldog,
    parse_devbg,
    parse_djinni,
    parse_jobtiger,
    parse_justjoin,
    parse_nofluff,
)
from job_assistant.services.eligibility import choose_board_jobs
from job_assistant.services.general_boards import (
    parse_arc,
    parse_hn,
    parse_linkedin,
    parse_relocate,
    parse_ycombinator,
)
from job_assistant.services.remote_boards import (
    parse_euremote,
    parse_fourdayweek,
    parse_weworkremotely,
    parse_workingnomads,
)
from tests.test_board_jobs import job


DEVBG = """
<div class="job-list-item" data-job-id="565608">
  <span class="company-name">Excelsior Works</span>
  <a href="https://dev.bg/company/jobads/excelsior-works-senior-frontend-engineer/">role</a>
  <h6 class="job-title">Senior Frontend Engineer</h6>
  <span class=" badge ">Fully Remote</span>
</div>
"""

JOBTIGER = """
<a href="/obiavi-za-rabota/full-stack-net-engineer-330020-1" class="jt-card">
  <h3 class="jt-card__title">Full-Stack .NET Engineer</h3>
  <div class="jt-card__company">A1 Bulgaria</div>
  <div class="jt-card__location">Sofia, Work from home</div>
</a>
"""

JUSTJOIN = """
<script type="application/ld+json">
{"mainEntity":{"itemListElement":[
  {"url":"https://justjoin.it/job-offer/acme-senior-frontend-engineer-remote","name":"Senior Frontend Engineer"},
  {"url":"https://justjoin.it/job-offer/acme-backend-warszawa","name":"Backend Engineer"}
]}}
</script>
"""

BULLDOG = """
<script id="__NEXT_DATA__" type="application/json">%s</script>
""" % json.dumps(
    {
        "props": {
            "pageProps": {
                "jobs": [
                    {
                        "id": "1-senior-frontend",
                        "position": "Senior Frontend Engineer",
                        "remote": True,
                        "company": {"name": "Luxoft"},
                        "technologyTags": ["React"],
                    },
                    {
                        "id": "2-office",
                        "position": "Senior Frontend Engineer",
                        "remote": False,
                        "company": {"name": "Office Co"},
                        "technologyTags": [],
                    },
                ]
            }
        }
    }
)

DJINNI = """
<script type="application/ld+json">%s</script>
""" % json.dumps(
    [
        {
            "@type": "JobPosting",
            "title": "Senior Frontend Engineer",
            "url": "https://djinni.co/jobs/1-senior-frontend/",
            "jobLocationType": "TELECOMMUTE",
            "description": "React from Europe.",
            "hiringOrganization": {"name": "TrueGroup"},
            "applicantLocationRequirements": {"address": {"addressRegion": "Europe"}},
        }
    ]
)

WWR = """<?xml version="1.0"?>
<rss><channel>
<item>
  <title>A.Team: Senior Frontend Engineer</title>
  <link>https://weworkremotely.com/remote-jobs/a-team-senior-frontend</link>
  <region>Anywhere in the World</region>
  <category>Front-End Programming</category>
  <description>Build React.</description>
</item>
</channel></rss>
"""

EUREMOTE = """
<a href="https://euremotejobs.com/job/acme-senior-frontend-engineer/">
  <h3>Senior Frontend Engineer</h3>
  <div class="company">Acme</div>
</a>
"""

FOURDAY = (
    r'\"id\":\"abc\",\"slug\":\"senior-frontend-engineer-at-acme\",'
    r'\"title\":\"Senior Frontend Engineer\",\"companyName\":\"Acme\"'
    " Remote · Europe"
)

LINKEDIN = """
<div data-entity-urn="urn:li:jobPosting:443">
  <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/443"></a>
  <h3 class="base-search-card__title">Senior Frontend Engineer</h3>
  <a class="hidden-nested-link" href="https://www.linkedin.com/company/acme">Acme</a>
  <span class="job-search-card__location">European Union</span>
</div>
"""

RELOCATE = """
<div class="job__info">
  <div class="job__company">Acme</div>
  <div class="job__title"><a href="/remote/remote/acme/senior-frontend-engineer"><b>Senior Frontend Engineer</b></a></div>
</div>
<div class="job__info">
  <div class="job__company">Tokyo Co</div>
  <div class="job__title"><a href="/japan/tokyo/tokyo-co/senior-frontend-engineer"><b>Senior Frontend Engineer</b></a></div>
</div>
"""


class ExtraBoardParserTests(unittest.TestCase):
    def test_devbg_marks_fully_remote_roles_in_bulgaria(self):
        jobs = parse_devbg(DEVBG)
        self.assertEqual(jobs[0]["title"], "Senior Frontend Engineer")
        self.assertEqual(jobs[0]["company"], "Excelsior Works")
        self.assertIn("Bulgaria", jobs[0]["location"])
        self.assertIn("remote", jobs[0]["location"].lower())

    def test_jobtiger_keeps_sofia_work_from_home(self):
        jobs = parse_jobtiger(JOBTIGER)
        self.assertEqual(jobs[0]["company"], "A1 Bulgaria")
        self.assertIn("Sofia", jobs[0]["location"])
        self.assertTrue(jobs[0]["url"].startswith("https://www.jobtiger.bg/"))

    def test_nofluff_keeps_remote_and_skips_office(self):
        jobs = parse_nofluff(
            {
                "postings": [
                    {
                        "id": "fe-1",
                        "title": "Senior Frontend Engineer",
                        "name": "Univio",
                        "url": "senior-frontend-univio-remote",
                        "fullyRemote": True,
                        "seniority": ["Senior"],
                        "location": {"places": [{"city": "Remote"}]},
                        "salary": {"from": 6000, "to": 8000, "currency": "EUR", "period": "Month"},
                    },
                    {
                        "id": "office",
                        "title": "Senior Frontend Engineer",
                        "name": "Office",
                        "url": "office",
                        "fullyRemote": False,
                        "location": {"places": [{"city": "Krakow", "country": {"name": "Poland"}}]},
                    },
                ]
            }
        )
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "Univio")
        self.assertEqual(jobs[0]["salary_min"], 6000)
        self.assertIn("Remote", jobs[0]["location"])

    def test_justjoin_keeps_remote_urls_only(self):
        jobs = parse_justjoin(JUSTJOIN)
        self.assertEqual([job["title"] for job in jobs], ["Senior Frontend Engineer"])

    def test_bulldog_keeps_remote_jobs(self):
        jobs = parse_bulldog(BULLDOG)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "Luxoft")
        self.assertIn("React", jobs[0]["tags"])

    def test_djinni_reads_job_posting(self):
        jobs = parse_djinni(DJINNI)
        self.assertEqual(jobs[0]["company"], "TrueGroup")
        self.assertIn("Europe", jobs[0]["location"])

    def test_weworkremotely_splits_company_and_role(self):
        jobs = parse_weworkremotely(WWR)
        self.assertEqual(jobs[0]["company"], "A.Team")
        self.assertEqual(jobs[0]["title"], "Senior Frontend Engineer")

    def test_working_nomads_prefixes_remote(self):
        jobs = parse_workingnomads(
            [
                {
                    "title": "Senior Frontend Engineer",
                    "company_name": "Lemon.io",
                    "url": "https://www.workingnomads.com/job/go/1/",
                    "location": "Europe",
                    "tags": "react,typescript",
                    "description": "<p>React</p>",
                }
            ]
        )
        self.assertEqual(jobs[0]["location"], "Remote, Europe")
        self.assertEqual(jobs[0]["tags"], ["react", "typescript"])

    def test_eu_remote_reads_the_card(self):
        jobs = parse_euremote(EUREMOTE)
        self.assertEqual(jobs[0]["company"], "Acme")
        self.assertIn("Europe", jobs[0]["location"])

    def test_fourdayweek_reads_remote_flight_data(self):
        jobs = parse_fourdayweek(FOURDAY)
        self.assertEqual(jobs[0]["company"], "Acme")
        self.assertIn("Europe", jobs[0]["location"])

    def test_linkedin_guest_card(self):
        jobs = parse_linkedin(LINKEDIN)
        self.assertEqual(jobs[0]["company"], "Acme")
        self.assertTrue(jobs[0]["location"].lower().startswith("remote"))

    def test_arc_skips_us_only_by_leaving_the_country_on_the_location(self):
        jobs = parse_arc(
            {
                "arcJobs": [
                    {
                        "randomKey": "abc",
                        "title": "Senior Frontend Engineer",
                        "urlString": "senior-frontend",
                        "requiredCountries": [],
                        "company": {},
                    }
                ],
                "externalJobs": [
                    {
                        "randomKey": "us",
                        "title": "Senior React Engineer",
                        "urlString": "us-react",
                        "requiredCountries": ["US"],
                        "company": {"name": "States Co"},
                    }
                ],
            }
        )
        self.assertEqual(jobs[0]["location"], "Remote")
        self.assertEqual(jobs[1]["location"], "Remote, United States")

    def test_ycombinator_keeps_remote_roles(self):
        page = {
            "props": {
                "jobs": [
                    {
                        "id": 9,
                        "title": "Frontend Engineer",
                        "location": "Remote",
                        "companyName": "Middesk",
                    },
                    {
                        "id": 10,
                        "title": "Frontend Engineer",
                        "location": "San Francisco",
                        "companyName": "Office",
                    },
                ]
            }
        }
        html = f'<div data-page="{escape(json.dumps(page))}"></div>'
        jobs = parse_ycombinator(html)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "Middesk")

    def test_hacker_news_comment_becomes_a_remote_role(self):
        jobs = parse_hn(
            [
                {
                    "objectID": "42",
                    "comment_text": "Acme | Remote\nSenior Frontend Engineer, React",
                }
            ]
        )
        self.assertEqual(jobs[0]["company"], "Acme")
        self.assertIn("Frontend", jobs[0]["title"])

    def test_relocate_keeps_remote_path_open(self):
        jobs = parse_relocate(RELOCATE)
        remote = [item for item in jobs if item["location"] == "Remote"]
        office = [item for item in jobs if item["location"] != "Remote"]
        self.assertEqual(len(remote), 1)
        self.assertEqual(office[0]["location"].lower().startswith("japan") or "Japan" in office[0]["location"], True)

    def test_bulgaria_remote_is_eligible_and_poland_only_is_not(self):
        bulgaria = job(
            id="bg",
            url="https://example.com/bg",
            location="Remote, Sofia, Bulgaria",
            score=0.8,
        )
        poland = job(
            id="pl",
            url="https://example.com/pl",
            company="Polish Co",
            location="Remote, Poland",
            score=0.8,
        )
        chosen, _stats = choose_board_jobs([bulgaria, poland], set())
        self.assertEqual([item["id"] for item in chosen], ["bg"])


if __name__ == "__main__":
    unittest.main()
