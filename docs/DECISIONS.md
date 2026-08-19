# Decisions

Record **what we chose and why**. Newest first. One short entry per decision.

Format:

```
## YYYY-MM-DD — Title
Choice: ...
Why: ...
Rejected: ... (optional)
```

---

## 2026-08-19 — Cheap Haiku, one tailor request

Choice: Default `ANTHROPIC_MODEL=claude-haiku-4-5`. Optimize is a single structured call (tailor + human voice). Leftover clichés are stripped locally. No second humanize request.

Why: Sonnet + a follow-up pass was ~5¢ per job. Haiku is the cheap tier; one round-trip is enough.

## 2026-08-19 — Anthropic for CV tailor

Choice: `get_llm()` uses `ChatAnthropic` with `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL`.

Why: OpenAI account was unbilled. Tailor still needs a chat model; Anthropic is the wired provider now.

Rejected: Keeping OpenAI as the optimize backend.

## 2026-08-18 — No personal location or phone on the CV

Choice: Contact header is email only. Strip location/phone from the source CV, Word downloads, and any tailored output.

Why: Keep Tehran/phone off applications. Employer cities in experience (e.g. Hamta, Tehran) stay.

## 2026-08-18 — Local ATS check in the UI (no OpenAI)

Choice: `evaluate_ats` scores parseability + JD skill overlap. UI **Check ATS** (`POST /api/ats`) uses the tailored resume for that listing, or the original CV if none exists. Pass = ATS score ≥ 70 and format ≥ 70.

Why: Optimize is paused until the OpenAI account is billed. ATS pass/fail is still useful against the current resume. A real vendor ATS is not available; heuristics are explicit and free.

Rejected: Calling the LLM evaluate node (same paid API as optimize).

## 2026-08-18 — Resume downloads are Word .docx, not PDF

Choice: Convert markdown CVs to `.docx` on download (`cv_docx.markdown_to_docx`). Source of truth stays `data/alireza_tahani_cv.md` / `output/optimized_cv.md`.

Why: Job sites and ATS prefer Word. Markdown is awkward to submit; PDF is gitignored and weaker for parsing.

Rejected: Shipping PDF; downloading raw markdown.

## 2026-08-18 — Optimize CV from the selected JD, then humanize

Choice: `optimize_cv` rewrites the resume for one job using only skills already on the CV. A second pass strips AI-sounding phrasing. UI “Tailor resume to this JD” calls `POST /api/optimize` with `job_id` (no refetch). CLI `--until optimize` uses the top-ranked job. Output: `output/optimized_cv.md`.

Why: Match the JD without inventing experience, and reduce ATS/AI-detector flags. Tailoring is per listing, so the UI should not re-run fetch.

Rejected: Full-graph optimize on every refresh; stuffing JD keywords that are not on the CV.

## 2026-08-18 — Rank jobs against the CV, not salary/title prefs

Choice: `sort_jobs` scores listings with `cv_matcher` (skill overlap, frontend/full-stack/senior fit, penalties for PHP/.NET/etc.). Scores and `matched_skills` show in the UI.

Why: Preferences alone ranked noisy boards poorly. The resume is the actual filter.

## 2026-08-18 — Local static UI on Python stdlib server

Choice: Serve `frontend/` from `job_assistant.web` (`ThreadingHTTPServer` on port 8765). No React/Vite.

Why: One-person tool; keep the stack small. The graph already runs in Python.

## 2026-08-18 — Web fetch still stops after sort

Choice: UI “Fetch & rank” calls `build_graph(until="sort")`. Optimize is a separate button/API.

Why: Browsing ranked JDs is the interactive loop. Rewriting the CV is opt-in per job.

## 2026-08-18 — Default source Himalayas, worldwide-only

Choice: Default `--source himalayas`. Drop listings that are not worldwide / all timezones.

Why: Target is fully remote, timezone-unrestricted roles. Himalayas has a public remote-jobs API.

## 2026-08-18 — LangGraph as the workflow

Choice: Nodes in `src/job_assistant/nodes/`, state in `state.py`, graph in `graph.py`.

Why: Fetch / rank / rewrite / score is a staged pipeline with optional early stop (`--until`).
