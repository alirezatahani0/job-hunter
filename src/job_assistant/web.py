from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from job_assistant.graph import build_graph
from job_assistant.main import DEFAULT_CV
from job_assistant.nodes.apply_job import application_for, apply_to_job, load_applications
from job_assistant.nodes.write_cover_letter import cover_for, write_cover_letter_node
from job_assistant.nodes.optimize_cv import optimize_cv_node
from job_assistant.services.ats_check import evaluate_ats
from job_assistant.services.cv_docx import DOCX_CONTENT_TYPE, markdown_to_docx
from job_assistant.services.cv_loader import load_cv, strip_private_contact
from job_assistant.services.eligibility import is_open_to_applicant
from job_assistant.services.remote import is_remote_job

ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT / "VERSION"
FRONTEND = ROOT / "frontend"
OUTPUT = ROOT / "output"
OPTIMIZED_JSON = OUTPUT / "optimized.json"
ATS_JSON = OUTPUT / "ats.json"
JOB_FILES = (
    OUTPUT / "himalayas_jobs.json",
    OUTPUT / "jobs.json",
    OUTPUT / "wellfound_jobs.json",
    OUTPUT / "glassdoor_jobs.json",
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
    applied = {item.get("job_id"): item for item in load_applications()}
    tagged = []
    for job in jobs:
        if not is_remote_job(job) or not is_open_to_applicant(job):
            continue
        row = dict(job)
        record = applied.get(row.get("id"))
        if record:
            submitted = record.get("status") == "submitted" or record.get("submitted") is True
            row["applied"] = submitted
            row["application_status"] = "submitted" if submitted else "ready"
            row["applied_at"] = record.get("applied_at") or record.get("prepared_at")
        tagged.append(row)
    return {
        "count": len(tagged),
        "jobs": tagged,
        "source_file": str(path.relative_to(ROOT)),
    }


def load_optimized() -> dict:
    if not OPTIMIZED_JSON.exists():
        return {"updated_cv": "", "changes_made": [], "job": None}
    payload = json.loads(OPTIMIZED_JSON.read_text(encoding="utf-8"))
    if payload.get("updated_cv"):
        payload["updated_cv"] = strip_private_contact(payload["updated_cv"])
    return payload


def _safe_filename(value: str, fallback: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in value)
    cleaned = cleaned.strip(".-") or fallback
    return cleaned[:80]


def original_resume_markdown() -> str:
    path = ROOT / DEFAULT_CV
    if not path.exists():
        return ""
    return load_cv(path)


def optimized_resume_markdown() -> str:
    payload = load_optimized()
    text = (payload.get("updated_cv") or "").strip()
    if text:
        return text
    path = OUTPUT / "optimized_cv.md"
    if path.exists():
        return strip_private_contact(path.read_text(encoding="utf-8"))
    return ""


def original_resume_filename() -> str:
    return "Alireza_Tahani_CV.docx"


def optimized_resume_filename() -> str:
    job = load_optimized().get("job") or {}
    company = _safe_filename(str(job.get("company") or ""), "job")
    return f"Alireza_Tahani_CV-{company}.docx"


def _base_state(job: dict | None = None) -> dict:
    cv_path = ROOT / DEFAULT_CV
    base_cv = load_cv(cv_path) if cv_path.exists() else " "
    return {
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
            "source": "boards",
            "himalayas_pages": 3,
            "worldwide_only": True,
        },
        "base_cv": base_cv,
        "max_jobs": 40,
        "jobs": [],
        "sorted_jobs": [],
        "selected_job": job,
        "updated_cv": "",
        "cv_changes": [],
        "evaluation": None,
        "cover_letter": "",
        "application_path": "",
        "output_path": "",
        "messages": [],
    }


def fetch_jobs() -> dict:
    app = build_graph(until="sort")
    result = app.invoke(_base_state())
    jobs = result.get("jobs") or []
    return {
        "count": len(jobs),
        "jobs": jobs,
        "messages": result.get("messages") or [],
    }


def load_ats() -> dict:
    if not ATS_JSON.exists():
        return {"evaluation": None, "job": None, "cv_source": None}
    return json.loads(ATS_JSON.read_text(encoding="utf-8"))


def _selected_job(job_id: str | None) -> dict:
    jobs = load_saved_jobs()["jobs"]
    selected = jobs[0] if jobs else None
    if job_id:
        selected = next((job for job in jobs if job.get("id") == job_id), selected)
    if not selected:
        raise ValueError("No saved job. Fetch jobs first.")
    return selected


def resume_for_job(job: dict) -> tuple[str, str]:
    """Prefer tailored CV for this listing; otherwise the original."""
    payload = load_optimized()
    tailored = (payload.get("updated_cv") or "").strip()
    if tailored and payload.get("job", {}).get("id") == job.get("id"):
        return tailored, "optimized"
    original = original_resume_markdown().strip()
    if not original:
        raise ValueError("No resume found to check.")
    return original, "original"


def check_ats(job_id: str | None) -> dict:
    selected = _selected_job(job_id)
    cv_text, cv_source = resume_for_job(selected)
    evaluation = evaluate_ats(cv_text, selected)
    payload = {
        "job": {
            "id": selected.get("id"),
            "title": selected.get("title"),
            "company": selected.get("company"),
            "url": selected.get("url"),
        },
        "cv_source": cv_source,
        "evaluation": evaluation,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ATS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def write_cover(job_id: str | None) -> dict:
    selected = _selected_job(job_id)
    cv_text, cv_source = resume_for_job(selected)
    state = _base_state(selected)
    if cv_source == "optimized":
        state["updated_cv"] = cv_text
    result = write_cover_letter_node(state)
    letter = result.get("cover_letter") or ""
    if not letter:
        raise ValueError("; ".join(result.get("messages") or ["Cover letter failed."]))
    return {
        "job": {
            "id": selected.get("id"),
            "title": selected.get("title"),
            "company": selected.get("company"),
            "url": selected.get("url"),
        },
        "cv_source": cv_source,
        "cover_letter": letter,
        "cover_path": result.get("application_path"),
        "messages": result.get("messages") or [],
    }


def apply_job(job_id: str | None) -> dict:
    selected = _selected_job(job_id)
    cv_text, cv_source = resume_for_job(selected)
    existing = cover_for(selected.get("id"))
    saved = apply_to_job(
        selected,
        matched=list(selected.get("matched_skills") or []),
        cv_source=cv_source,
        cover_letter=(existing or {}).get("cover_letter") or "",
        cv_text=cv_text,
    )
    return {
        "job": {
            "id": selected.get("id"),
            "title": selected.get("title"),
            "company": selected.get("company"),
            "url": selected.get("url"),
        },
        "apply_url": saved.get("url"),
        "cv_source": saved.get("cv_source"),
        "cover_letter": saved.get("cover_letter"),
        "status": saved.get("status") or "ready",
        "submitted": bool(saved.get("submitted")),
        "prepared_at": saved.get("prepared_at"),
        "cover_path": saved.get("cover_path"),
        "resume_path": saved.get("resume_path"),
    }


def optimize_job(job_id: str | None) -> dict:
    selected = _selected_job(job_id)
    result = optimize_cv_node(_base_state(selected))
    return {
        "job": {
            "id": selected.get("id"),
            "title": selected.get("title"),
            "company": selected.get("company"),
            "url": selected.get("url"),
        },
        "updated_cv": result.get("updated_cv") or "",
        "changes_made": result.get("cv_changes") or [],
        "output_path": result.get("output_path"),
        "messages": result.get("messages") or [],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        print(f"[web] {self.address_string()} {format % args}")

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_docx(self, markdown: str, filename: str, missing: str) -> None:
        if not markdown.strip():
            self._send_json(404, {"error": missing})
            return
        self._send(
            200,
            markdown_to_docx(markdown),
            DOCX_CONTENT_TYPE,
            extra_headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/jobs":
            self._send_json(200, load_saved_jobs())
            return
        if path == "/api/version":
            version = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else ""
            self._send_json(200, {"version": version})
            return
        if path == "/api/report":
            report = OUTPUT / "reports" / "latest.md"
            text = report.read_text(encoding="utf-8") if report.exists() else ""
            self._send_json(200, {"text": text})
            return
        if path == "/api/optimized":
            self._send_json(200, load_optimized())
            return
        if path == "/api/ats":
            self._send_json(200, load_ats())
            return
        if path == "/api/applications":
            self._send_json(200, {"applications": load_applications()})
            return
        if path == "/api/cover":
            job_id = (query.get("job_id") or [None])[0]
            record = cover_for(job_id) or application_for(job_id)
            if not record or not record.get("cover_letter"):
                self._send_json(404, {"error": "No cover letter for this job yet."})
                return
            self._send_json(200, {**record, "job": {"id": job_id}})
            return
        if path in {"/api/apply/letter", "/api/cover/letter"}:
            job_id = (query.get("job_id") or [None])[0]
            record = cover_for(job_id) or application_for(job_id)
            if not record or not record.get("cover_letter"):
                self._send_json(404, {"error": "No cover letter. Write one first."})
                return
            company = _safe_filename(str(record.get("company") or "job"), "job")
            cover_path = record.get("cover_path") or ""
            if str(cover_path).endswith(".docx") and Path(cover_path).is_file():
                body = Path(cover_path).read_bytes()
            else:
                from job_assistant.nodes.write_cover_letter import letter_to_docx

                body = letter_to_docx(str(record["cover_letter"]))
            self._send(
                200,
                body,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                extra_headers={
                    "Content-Disposition": f'attachment; filename="cover-{company}.docx"',
                },
            )
            return
        if path == "/api/resume/original":
            self._send_docx(
                original_resume_markdown(),
                original_resume_filename(),
                "Original resume not found.",
            )
            return
        if path == "/api/resume/optimized":
            self._send_docx(
                optimized_resume_markdown(),
                optimized_resume_filename(),
                "No optimized resume yet. Tailor this JD first.",
            )
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/fetch":
                self._send_json(200, fetch_jobs())
                return
            if path == "/api/optimize":
                body = self._read_json()
                self._send_json(200, optimize_job(body.get("job_id")))
                return
            if path == "/api/cover":
                body = self._read_json()
                self._send_json(200, write_cover(body.get("job_id")))
                return
            if path == "/api/ats":
                body = self._read_json()
                self._send_json(200, check_ats(body.get("job_id")))
                return
            if path == "/api/apply":
                body = self._read_json()
                self._send_json(200, apply_job(body.get("job_id")))
                return
            self._send_json(404, {"error": "Not found"})
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
    load_dotenv(ROOT / ".env")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Job board UI: http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
