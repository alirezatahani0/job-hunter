from __future__ import annotations

import os
import re

import httpx

TRELLO_API = "https://api.trello.com/1"
_URL_IN_TEXT = re.compile(r"https?://\S+")


def parse_list_map(raw: str) -> dict[str, str]:
    lists: dict[str, str] = {}
    for part in (raw or "").split(","):
        part = part.strip()
        if ":" not in part:
            continue
        name, list_id = part.split(":", 1)
        name = name.strip()
        list_id = list_id.strip()
        if name and list_id:
            lists[name] = list_id
    return lists


def urls_on_card(card: dict) -> set[str]:
    found = set()
    direct = (card.get("url") or "").strip()
    if direct.startswith("http"):
        found.add(direct.rstrip(").,"))
    for match in _URL_IN_TEXT.findall(card.get("desc") or ""):
        found.add(match.rstrip(").,"))
    return found


class TrelloClient:
    def __init__(
        self,
        *,
        key: str,
        token: str,
        board_id: str,
        lists: dict[str, str],
        http: httpx.Client | None = None,
    ) -> None:
        self.key = key
        self.token = token
        self.board_id = board_id
        self.lists = lists
        self.http = http or httpx.Client(timeout=30.0)

    def _params(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        params = {"key": self.key, "token": self.token}
        if extra:
            params.update(extra)
        return params

    def open_cards(self) -> list[dict]:
        response = self.http.get(
            f"{TRELLO_API}/boards/{self.board_id}/cards",
            params=self._params({"fields": "name,desc,url,idList", "filter": "open"}),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def cards_in(self, list_name: str) -> list[dict]:
        list_id = self.lists[list_name]
        response = self.http.get(
            f"{TRELLO_API}/lists/{list_id}/cards",
            params=self._params({"fields": "name,desc,url,idList", "filter": "open"}),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def move_card(self, card_id: str, list_name: str) -> dict:
        response = self.http.put(
            f"{TRELLO_API}/cards/{card_id}",
            params=self._params({"idList": self.lists[list_name]}),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def add_comment(self, card_id: str, text: str) -> dict:
        response = self.http.post(
            f"{TRELLO_API}/cards/{card_id}/actions/comments",
            params=self._params({"text": text}),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def attach_file(self, card_id: str, path: str) -> dict:
        from pathlib import Path

        file_path = Path(path)
        with file_path.open("rb") as handle:
            response = self.http.post(
                f"{TRELLO_API}/cards/{card_id}/attachments",
                params=self._params({"name": file_path.name}),
                files={"file": (file_path.name, handle, "application/octet-stream")},
            )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def create_card(self, *, list_name: str, name: str, desc: str, url: str) -> dict:
        list_id = self.lists[list_name]
        response = self.http.post(
            f"{TRELLO_API}/cards",
            params=self._params(
                {
                    "idList": list_id,
                    "name": name,
                    "desc": desc,
                    "urlSource": url,
                }
            ),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}


def trello_from_env() -> TrelloClient:
    key = os.environ.get("TRELLO_API_KEY", "").strip()
    token = os.environ.get("TRELLO_TOKEN", "").strip()
    board_id = os.environ.get("TRELLO_BOARD_ID", "").strip()
    lists = parse_list_map(os.environ.get("TRELLO_LISTS", ""))
    missing = [
        name
        for name, value in (
            ("TRELLO_API_KEY", key),
            ("TRELLO_TOKEN", token),
            ("TRELLO_BOARD_ID", board_id),
            ("TRELLO_LISTS", lists),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing Trello settings: {', '.join(missing)}")
    if "Found" not in lists:
        raise RuntimeError("TRELLO_LISTS has no Found column")
    return TrelloClient(key=key, token=token, board_id=board_id, lists=lists)
