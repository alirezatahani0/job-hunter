from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from job_assistant.graph import build_graph
from job_assistant.main import DEFAULT_CV
from job_assistant.services.cv_loader import load_cv

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
OUTPUT = ROOT / "output"
JOB_FILES = (
    OUTPUT / "himalayas_jobs.json",
    OUTPUT / "jobs.json",
    OUTPUT / "wellfound_jobs.json",
)


def _latest_jobs_file() -> Path | None:
    existing = [path for path in JOB_FILES if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def load_saved_jobs() -> dict:
    path = _latest_jobs_file()
    if not path:
        return {"count": 0, "jobs": [], "source_file": None}
    payload = json.loads(path.read_text(encoding="utf-8"))
    jobs = payload.get("jobs") if isinstance(payload, dict) else payload
    if not isinstance(jobs, list):
        jobs = []
    return {
        "count": len(jobs),
        "jobs": jobs,
        "source_file": str(path.relative_to(ROOT)),
    }


def fetch_jobs() -> dict:
    cv_path = ROOT / DEFAULT_CV
    base_cv = load_cv(cv_path) if cv_path.exists() else " "
    app = build_graph(fetch_only=True)
    result = app.invoke(
        {
            "preferences": {
                "query": "react",
                "titles": [
                    "Senior Frontend Engineer",
                    "Lead Frontend Engineer",
                    "Frontend Engineer",
                    "Senior Full-Stack Engineer",
                    "Full-Stack Engineer",
                ],
                "location": "Remote",
                "tags": ["react", "typescript", "nextjs", "frontend"],
                "min_salary": None,
                "max_jobs": 40,
                "source": "himalayas",
                "himalayas_pages": 3,
                "worldwide_only": True,
            },
            "base_cv": base_cv,
            "max_jobs": 40,
            "jobs": [],
            "sorted_jobs": [],
            "selected_job": None,
            "updated_cv": "",
            "evaluation": None,
            "output_path": "",
            "messages": [],
        }
    )
    jobs = result.get("jobs") or []
    return {
        "count": len(jobs),
        "jobs": jobs,
        "messages": result.get("messages") or [],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        print(f"[web] {self.address_string()} {format % args}")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/jobs":
            self._send_json(200, load_saved_jobs())
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/fetch":
            self._send_json(404, {"error": "Not found"})
            return
        try:
            payload = fetch_jobs()
            self._send_json(200, payload)
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": str(exc)})

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (FRONTEND / relative).resolve()
        if FRONTEND not in target.parents and target != FRONTEND:
            self._send_json(403, {"error": "Forbidden"})
            return
        if not target.exists() or not target.is_file():
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self._send(200, target.read_bytes(), content_type)


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Job board UI: http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
