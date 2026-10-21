import unittest

from job_assistant.nodes.advance_board import advance_found_cards, posting_url


class FakeBoard:
    def __init__(self):
        self.lists = {
            "Found": "found",
            "Tailored": "tailored",
            "Applied": "applied",
            "Needs you": "attention",
        }
        self.cards = [
            {
                "id": "c1",
                "name": "Frontend Engineer — Perena",
                "desc": "URL: https://example.com/perena\nCompany: Perena",
                "idList": "found",
            }
        ]
        self.moves = []
        self.comments = []
        self.attachments = []

    def cards_in(self, list_name):
        list_id = self.lists[list_name]
        return [card for card in self.cards if card["idList"] == list_id]

    def move_card(self, card_id, list_name):
        self.moves.append((card_id, list_name))
        for card in self.cards:
            if card["id"] == card_id:
                card["idList"] = self.lists[list_name]

    def add_comment(self, card_id, text):
        self.comments.append((card_id, text))

    def attach_file(self, card_id, path):
        self.attachments.append((card_id, path))


def job():
    return {
        "id": "perena",
        "title": "Frontend Engineer",
        "company": "Perena",
        "location": "Worldwide",
        "tags": ["react"],
        "salary_min": None,
        "salary_max": None,
        "salary_text": None,
        "url": "https://example.com/perena",
        "description": "Build React interfaces.",
    }


class AdvanceBoardTests(unittest.TestCase):
    def test_posting_url_comes_from_the_card_description(self):
        self.assertEqual(
            posting_url({"desc": "URL: https://example.com/perena\nMatch: 80%"}),
            "https://example.com/perena",
        )

    def test_tailor_then_apply_moves_the_card(self):
        board = FakeBoard()
        calls = []

        def tailor(listing, base_cv):
            calls.append(("tailor", listing["id"], base_cv))
            return {"updated_cv": "tailored resume"}

        def apply(listing, cv_text):
            calls.append(("apply", listing["id"], cv_text))
            return {"resume_path": "output/resume_Perena.docx", "cover_path": "output/cover_Perena.md"}

        messages = advance_found_cards(
            [job()],
            "base cv",
            client=board,
            tailor=tailor,
            apply=apply,
        )
        self.assertEqual([name for _card, name in board.moves], ["Tailored"])
        self.assertEqual(calls[0][0], "tailor")
        self.assertEqual(calls[1][0], "apply")
        self.assertEqual(
            board.attachments,
            [("c1", "output/resume_Perena.docx"), ("c1", "output/cover_Perena.md")],
        )
        self.assertTrue(any("Tailored" in message for message in messages))
        self.assertTrue(any("submit" in message.lower() for message in messages))
        self.assertTrue(any("submit" in text.lower() for _card, text in board.comments))

    def test_tailor_failure_moves_the_card_to_needs_you(self):
        board = FakeBoard()
        applied = []

        def tailor(listing, base_cv):
            raise RuntimeError("model down")

        def apply(listing, cv_text):
            applied.append(listing["id"])
            return {}

        advance_found_cards([job()], "base cv", client=board, tailor=tailor, apply=apply)
        self.assertEqual([name for _card, name in board.moves], ["Needs you"])
        self.assertEqual(applied, [])
        self.assertIn("model down", board.comments[0][1])

    def test_submitted_packet_moves_the_card_to_applied(self):
        board = FakeBoard()

        def tailor(listing, base_cv):
            return {"updated_cv": "tailored resume"}

        def apply(listing, cv_text):
            return {
                "submitted": True,
                "resume_path": "output/resume_Perena.docx",
                "cover_path": "output/cover_Perena.docx",
                "submit_detail": "Submitted the Dover form.",
            }

        messages = advance_found_cards(
            [job()],
            "base cv",
            client=board,
            tailor=tailor,
            apply=apply,
        )
        self.assertEqual([name for _card, name in board.moves], ["Tailored", "Applied"])
        self.assertIn("Submitted the Dover form.", board.comments[-1][1])
        self.assertTrue(any(message.startswith("Applied:") for message in messages))


if __name__ == "__main__":
    unittest.main()
