# Status

Living snapshot of what works now. Keep this short. Update at the end of a session.

Last updated: 2026-08-18

## Working

- LangGraph pipeline: fetch → sort → optimize CV → evaluate → print
- CLI: `python -m job_assistant.main` with `--source` and `--until fetch|sort|optimize|end`
- Himalayas fetch filtered to worldwide + unrestricted hiring timezones
- Sort ranks jobs against `data/alireza_tahani_cv.md` (skills + role fit). Contact header is **email only** (no location/phone on original or tailored downloads).
- Local UI at `:8765`: HUD-style board — list/search ranked jobs, match %, **Check ATS**, tailor/download Word
- ATS check: parseability + JD keyword overlap. Uses tailored CV if this job was optimized; otherwise the original. **PASS** if ATS score ≥ 70 and format is clean.
- Web “Fetch & rank” runs `until="sort"` → `output/himalayas_jobs.json`
- Web tailor runs `POST /api/optimize` → one `claude-haiku-4-5` call → `output/optimized_cv.md`

## In progress / next

- Evaluate node (ATS pass / AI-written flag) is in the UI via **Check ATS**; still local heuristics, not a vendor ATS
- Job search prefs (titles, tags, query `"react"`, max 40) are still hardcoded in `web.py`

## Known constraints

- Root venv (`bin/`, `lib/`) is gitignored; do not treat it as app code
- `output/` is gitignored — local job cache and tailored CVs, not source of truth
- Optimize fails without `.env` `ANTHROPIC_API_KEY`. Local ATS check does not need it.
