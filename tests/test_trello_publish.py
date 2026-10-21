import unittest

import httpx

from job_assistant.nodes.publish_board import publish_board_node
from job_assistant.services.trello import TrelloClient, parse_list_map


class ParseListMapTests(unittest.TestCase):
    def test_parses_names_that_contain_spaces(self):
        raw = "Needs you:abc,Found:def"
        self.assertEqual(parse_list_map(raw), {"Needs you": "abc", "Found": "def"})


class TrelloClientTests(unittest.TestCase):
    def test_create_card_posts_onto_the_named_list(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["url"] = str(request.url)
            return httpx.Response(200, json={"id": "c1", "url": "https://trello.com/c/c1"})

        http = httpx.Client(transport=httpx.MockTransport(handler))
        client = TrelloClient(
            key="k",
            token="t",
            board_id="board1",
            lists={"Found": "list-found"},
            http=http,
        )
        created = client.create_card(
            list_name="Found",
            name="Frontend Engineer — Acme",
            desc="URL: https://example.com/job",
            url="https://example.com/job",
        )
        self.assertEqual(created["id"], "c1")
        self.assertEqual(seen["method"], "POST")
        self.assertIn("/1/cards", seen["url"])
        self.assertIn("idList=list-found", seen["url"])
        self.assertIn("key=k", seen["url"])


class FakeTrello:
    def __init__(self):
        self.created = []

    def open_cards(self):
        return [{"url": "https://example.com/old", "desc": "URL: https://example.com/old", "name": "Old"}]

    def create_card(self, *, list_name, name, desc, url):
        self.created.append(
            {"list_name": list_name, "name": name, "desc": desc, "url": url}
        )
        return {"url": "https://trello.com/c/new"}


class PublishBoardTests(unittest.TestCase):
    def test_adds_a_new_match_to_found_and_skips_an_existing_url(self):
        fake = FakeTrello()
        result = publish_board_node(
            {
                "messages": [],
                "sorted_jobs": [
                    {
                        "id": "old",
                        "title": "Frontend Engineer",
                        "company": "Old Co",
                        "location": "Remote",
                        "tags": [],
                        "salary_min": None,
                        "salary_max": None,
                        "salary_text": None,
                        "url": "https://example.com/old",
                        "description": "Remote frontend role.",
                        "score": 0.9,
                    },
                    {
                        "id": "new",
                        "title": "Full-Stack Engineer",
                        "company": "New Co",
                        "location": "Worldwide",
                        "tags": [],
                        "salary_min": None,
                        "salary_max": None,
                        "salary_text": "USD 120,000",
                        "url": "https://example.com/new",
                        "description": "Worldwide full-stack role.",
                        "score": 0.7,
                    },
                ],
            },
            client=fake,
        )
        self.assertEqual(len(fake.created), 1)
        self.assertEqual(fake.created[0]["list_name"], "Found")
        self.assertEqual(fake.created[0]["url"], "https://example.com/new")
        self.assertIn("New Co", fake.created[0]["name"])
        self.assertTrue(any("Found" in message for message in result["messages"]))


if __name__ == "__main__":
    unittest.main()
