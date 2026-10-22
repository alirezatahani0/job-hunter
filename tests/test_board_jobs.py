import unittest

from job_assistant.services.eligibility import (
    card_description,
    card_name,
    choose_board_jobs,
    is_target_role,
    is_us_restricted,
    pays_with_crypto,
)


def job(**overrides):
    base = {
        "id": "1",
        "title": "Senior Frontend Engineer",
        "company": "Acme",
        "location": "Remote",
        "tags": ["react"],
        "salary_min": None,
        "salary_max": None,
        "salary_text": "USD 100,000",
        "url": "https://example.com/jobs/1",
        "description": "Build React interfaces for a worldwide remote team.",
        "score": 0.4,
    }
    base.update(overrides)
    return base


class EligibilityTests(unittest.TestCase):
    def test_worldwide_remote_is_not_us_restricted(self):
        self.assertFalse(is_us_restricted(job(location="Worldwide")))

    def test_us_location_is_restricted(self):
        self.assertTrue(is_us_restricted(job(location="Remote - United States")))
        self.assertTrue(is_us_restricted(job(location="USA")))

    def test_wellfound_us_acceptance_is_restricted(self):
        listing = job(location="Remote | Accepted: United States")
        self.assertTrue(is_us_restricted(listing))

    def test_us_based_note_is_restricted(self):
        listing = job(
            location="Remote | Cheyenne",
            description="The ideal candidate is ready on day one. (US Based)",
        )
        self.assertTrue(is_us_restricted(listing))

    def test_us_work_authorization_is_restricted(self):
        listing = job(
            location="Remote",
            description="You must be authorized to work in the United States.",
        )
        self.assertTrue(is_us_restricted(listing))

    def test_cryptography_is_not_crypto_pay(self):
        listing = job(description="We use cryptography to protect customer data.")
        self.assertFalse(pays_with_crypto(listing))

    def test_crypto_salary_is_crypto_pay(self):
        listing = job(salary_text="Paid in USDC", description="Compensation is paid in USDC.")
        self.assertTrue(pays_with_crypto(listing))

    def test_frontend_and_fullstack_are_target_roles(self):
        self.assertTrue(is_target_role(job(title="Senior Frontend Engineer")))
        self.assertTrue(is_target_role(job(title="Full-Stack Engineer")))
        self.assertTrue(is_target_role(job(title="React Developer")))
        self.assertFalse(is_target_role(job(title="Backend Engineer")))
        self.assertFalse(is_target_role(job(title="Senior Product Designer (Full-Stack)")))


class ChooseBoardJobsTests(unittest.TestCase):
    def test_crypto_pay_ranks_above_a_closer_match(self):
        crypto = job(
            id="crypto",
            url="https://example.com/crypto",
            title="Frontend Engineer",
            score=0.6,
            salary_text="Paid in USDC",
            description="Salary paid in USDC.",
        )
        closer = job(
            id="closer",
            url="https://example.com/closer",
            title="Senior Frontend Engineer",
            score=0.9,
        )
        chosen, _stats = choose_board_jobs([closer, crypto], set(), limit=1)
        self.assertEqual(chosen[0]["id"], "crypto")

    def test_skips_us_only_backend_and_existing_cards(self):
        keep = job(id="keep", url="https://example.com/keep", score=0.8)
        us = job(
            id="us",
            url="https://example.com/us",
            location="United States",
            score=0.99,
        )
        backend = job(
            id="backend",
            url="https://example.com/backend",
            title="Backend Engineer",
            score=0.99,
        )
        existing = job(id="old", url="https://example.com/old", score=0.99)
        chosen, stats = choose_board_jobs(
            [us, backend, existing, keep],
            {"https://example.com/old"},
            limit=5,
        )
        self.assertEqual([item["id"] for item in chosen], ["keep"])
        self.assertEqual(stats["dropped_us"], 1)
        self.assertEqual(stats["dropped_role"], 1)
        self.assertEqual(stats["dropped_existing"], 1)

    def test_country_locked_remote_is_left_off_the_board(self):
        india = job(
            id="india",
            url="https://example.com/india",
            location="Remote | Accepted: India",
            score=0.99,
        )
        europe = job(
            id="europe",
            url="https://example.com/europe",
            location="Remote | Accepted: Estonia, Europe, Germany, France",
            score=0.6,
        )
        chosen, stats = choose_board_jobs([india, europe], set(), limit=5)
        self.assertEqual(chosen, [])
        self.assertEqual(stats["dropped_region"], 2)

    def test_keeps_a_role_that_hires_from_anywhere(self):
        anywhere = job(
            id="anywhere",
            url="https://example.com/anywhere",
            location="Worldwide / all countries",
            hiring_timezones="All timezones",
            score=0.8,
        )
        europe = job(
            id="europe",
            url="https://example.com/europe",
            company="Europe Co",
            location="Remote, Europe",
            score=0.9,
        )
        listed = job(
            id="listed",
            url="https://example.com/listed",
            company="Listed Co",
            location="Remote",
            score=0.9,
            description="Locations: Spain, Portugal, and Bulgaria.",
        )
        timezone = job(
            id="timezone",
            url="https://example.com/timezone",
            company="Timezone Co",
            location="Remote",
            hiring_timezones="UTC+0 to UTC+3",
            score=0.9,
        )
        chosen, stats = choose_board_jobs([europe, listed, timezone, anywhere], set())
        self.assertEqual([item["id"] for item in chosen], ["anywhere"])
        self.assertEqual(stats["dropped_region"], 3)

    def test_keeps_one_role_per_company(self):
        first = job(
            id="a",
            company="Tether",
            url="https://example.com/a",
            score=0.9,
            salary_text="Paid in USDC",
            description="Salary paid in USDC.",
        )
        second = job(
            id="b",
            company="Tether",
            url="https://example.com/b",
            score=0.8,
            salary_text="Paid in USDC",
            description="Salary paid in USDC.",
        )
        other = job(
            id="c",
            company="Other",
            url="https://example.com/c",
            title="Frontend Engineer",
            score=0.6,
        )
        chosen, _stats = choose_board_jobs([first, second, other], set(), limit=3)
        self.assertEqual([item["id"] for item in chosen], ["a", "c"])

    def test_keeps_every_role_scoring_above_50_percent(self):
        strong = [
            job(
                id=str(index),
                company=f"Company {index}",
                url=f"https://example.com/{index}",
                score=0.51 + (index / 100),
            )
            for index in range(6)
        ]
        borderline = job(
            id="half",
            company="Half",
            url="https://example.com/half",
            score=0.5,
        )
        chosen, stats = choose_board_jobs([*strong, borderline], set())
        self.assertEqual(len(chosen), 6)
        self.assertNotIn("half", [item["id"] for item in chosen])
        self.assertEqual(stats["dropped_score"], 1)

    def test_unpaid_and_closed_country_lists_are_left_off(self):
        volunteer = job(
            id="volunteer",
            company="Solution Community",
            url="https://example.com/volunteer",
            title="AI Full Stack Engineer (Volunteer, unpaid)",
            score=0.95,
            description="This is an unpaid volunteer role.",
        )
        closed = job(
            id="closed",
            company="Spotter",
            url="https://example.com/closed",
            title="Remote FullStack Engineer",
            score=0.9,
            location="Remote",
            description="Locations: Argentina, India, Colombia, Mexico, Pakistan, Philippines.",
        )
        open_role = job(
            id="open",
            company="Open Co",
            url="https://example.com/open",
            score=0.8,
        )
        chosen, stats = choose_board_jobs([volunteer, closed, open_role], set())
        self.assertEqual([item["id"] for item in chosen], ["open"])
        self.assertEqual(stats["dropped_unpaid"], 1)
        self.assertEqual(stats["dropped_region"], 1)

    def test_card_text_includes_company_and_url(self):
        listing = job()
        self.assertIn("Acme", card_name(listing))
        self.assertIn("Senior Frontend Engineer", card_name(listing))
        text = card_description(listing)
        self.assertIn("https://example.com/jobs/1", text)
        self.assertIn("USD 100,000", text)


if __name__ == "__main__":
    unittest.main()
