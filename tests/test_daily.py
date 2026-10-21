import unittest

from job_assistant.nodes.daily import run_daily
from job_assistant.services.mail import MailMessage, decide, match_card, process_inbox


class DailyRunTests(unittest.TestCase):
    def test_runs_fetch_then_tailor_then_submit_then_mail(self):
        calls = []

        def step(name, text):
            def run():
                calls.append(name)
                return [text]

            return run

        messages = run_daily(
            fetch=step("fetch", "Found: 1"),
            advance=step("advance", "Applied: one"),
            submit=step("submit", "Tailored: waiting"),
            inbox=step("inbox", "Mail: none"),
        )

        self.assertEqual(calls, ["fetch", "advance", "submit", "inbox"])
        self.assertEqual(
            messages,
            ["Found: 1", "Applied: one", "Tailored: waiting", "Mail: none"],
        )

    def test_a_failed_fetch_still_reads_mail(self):
        calls = []

        def fetch():
            calls.append("fetch")
            raise RuntimeError("board down")

        def inbox():
            calls.append("inbox")
            return ["Mail: none"]

        messages = run_daily(
            fetch=fetch,
            advance=lambda: calls.append("advance") or [],
            submit=lambda: calls.append("submit") or [],
            inbox=inbox,
        )

        self.assertEqual(calls, ["fetch", "advance", "submit", "inbox"])
        self.assertIn("fetch failed: board down", messages)
        self.assertIn("Mail: none", messages)


class MailDecisionTests(unittest.TestCase):
    def test_newsletters_are_ignored(self):
        message = MailMessage(
            message_id="1",
            sender="alerts@glassdoor.com",
            subject="Your daily job alert",
            body="Unsubscribe from these emails.",
        )
        self.assertEqual(decide(message), "newsletter")

    def test_rejections_move_the_matching_card(self):
        message = MailMessage(
            message_id="2",
            sender="hiring@perena.com",
            subject="Your application at Perena",
            body="We decided to move forward with other candidates.",
        )
        cards = [
            {"id": "card-1", "name": "Frontend Engineer — Perena"},
            {"id": "card-2", "name": "Senior Fullstack Engineer — The Agile Monkeys"},
        ]
        self.assertEqual(decide(message), "rejection")
        self.assertEqual(match_card(message, cards)["id"], "card-1")

    def test_interview_invites_are_replied_to(self):
        message = MailMessage(
            message_id="3",
            sender="recruiter@example.com",
            subject="Interview for Frontend Engineer",
            body="Could we schedule a call next week?",
        )
        self.assertEqual(decide(message), "interview")

    def test_a_real_question_is_answered(self):
        message = MailMessage(
            message_id="4",
            sender="talent@example.com",
            subject="A question about your application",
            body="Could you confirm your earliest start date?",
        )
        self.assertEqual(decide(message), "question")

    def test_a_no_reply_rejection_still_counts(self):
        message = MailMessage(
            message_id="6",
            sender="no-reply@company.com",
            subject="Update on your application",
            body="Unfortunately we will be moving forward with other candidates.",
        )
        self.assertEqual(decide(message), "rejection")

    def test_inbox_replies_to_invites_and_leaves_newsletters(self):
        newsletter = MailMessage(
            message_id="n",
            sender="alerts@glassdoor.com",
            subject="Your daily job alert",
            body="Unsubscribe from these emails.",
        )
        invite = MailMessage(
            message_id="i",
            sender="recruiter@perena.com",
            subject="Interview for Frontend Engineer",
            body="Could we schedule a call?",
        )
        cards = [{"id": "card-1", "name": "Frontend Engineer — Perena"}]
        replied = []
        moved = []
        noted = []
        lines = process_inbox(
            [newsletter, invite],
            cards,
            reply=lambda message, body: replied.append((message.message_id, body)),
            move=lambda card: moved.append(card["id"]),
            note=lambda card, text: noted.append((card["id"], text)),
        )
        self.assertEqual(replied[0][0], "i")
        self.assertNotIn("5605", replied[0][1])
        self.assertEqual(moved, [])
        self.assertEqual(noted, [("card-1", "Replied to the interview invite.")])
        self.assertIn("Mail: left alone (Your daily job alert)", lines)

    def test_unknown_mail_is_left_alone(self):
        message = MailMessage(
            message_id="5",
            sender="friend@example.com",
            subject="Hello",
            body="Hope you are well.",
        )
        self.assertEqual(decide(message), "ignore")


if __name__ == "__main__":
    unittest.main()
