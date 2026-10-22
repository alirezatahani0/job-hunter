# Status

Living snapshot of what works now. Keep this short. Update at the end of a session.

Last updated: 2026-10-22

Current version: **v0.7.0** (`VERSION`, git tag). Each finished change bumps the version, commits, tags, and pushes.

## Working

- Trello board **Job Search**: https://trello.com/b/mrGM8eAo/job-search — columns Needs you, Found, Tailored, Applied, Replied, Interview, Rejected. `--until board` scores every fetched role and adds each new match above 50%: crypto pay first, one company each, frontend/full-stack, fully remote, and open to any location. Europe-only, Bulgaria-only, timezone-limited, US-only, and country-list roles stay off. There is no daily card cap.
- LangGraph pipeline: fetch → sort → optimize CV → evaluate → cover letter → apply → print. `--until board` stops after publishing Found cards.
- CLI: `python -m job_assistant.main` with `--source boards` (or one board name) and `--until fetch|sort|board|advance|submit|daily|optimize|cover|apply|end`
- `--until daily` fetches, scores every listing, adds every match above 50%, tailors and submits what it can, then reads mail. It writes `output/reports/latest.md`. launchd `com.alireza.job-assistant.daily` runs it every day at 10:00 and 15:00 Europe/London. The Mac has to be awake. Logs: `output/daily.log`.
- Default fetch is `boards`, in this order: Eastern Europe and Bulgaria (DEV.bg, Jobs.bg, JobTiger, Rabota.bg, No Fluff Jobs, Just Join IT, Bulldogjob, Djinni), then remote-first boards (We Work Remotely, 4 Day Week, JustRemote, Working Nomads, EU Remote Jobs, Dynamite Jobs, Himalayas, Wellfound, Remote OK, Remotive), then general tech boards (LinkedIn, Indeed, Welcome to the Jungle, Arc, Y Combinator, Hacker News, Landing.jobs, Relocate.me, Glassdoor). A bot check, a page with no public listings, or a board that does not answer within 150 seconds is skipped and named in the run notes. A role is kept only when it is fully remote and does not care where the person is.
- 2026-10-19 ranked list is `output/jobs.json`. Himalayas, Wellfound, Remote OK, and Remotive returned remote roles. Glassdoor HTTP fetch is still blocked. Claude packets are status **ready** for hard.coded, Vagmine Tech IT, Casino Alpha, Apiphany AI, and Halliday, plus the earlier worldwide batch.
- Sort ranks jobs against `data/alireza_tahani_cv.md` (skills + role fit). Contact is email only. Experience headers: SAP (Germany) / Identity Global (UK); Fixefy.io. Claude/Cursor + Job Assistant project — no fake healthcare/HIPAA.
- Local UI: **Apply** runs only for jobs that are fully remote and open to any location. It saves the cover letter and Word resume, then submits a Dover or Recruitee form when that form can be completed. The chip says Applied only after the site accepts it.
- ATS check: parseability + JD keyword overlap. Uses tailored CV if this job was optimized; otherwise the original. **PASS** if ATS score ≥ 70 and format is clean.
- Web “Fetch & rank” runs `until="sort"` → `output/himalayas_jobs.json`
- Web tailor runs `POST /api/optimize` → one `claude-haiku-4-5` call → `output/optimized_cv.md`
- Web cover letter runs `POST /api/cover` → one Haiku call → `output/cover_letters.json`
- Open answers for repeat form questions live in `data/form_answers.md`. The same text is copied onto the Trello card as a comment.

## In progress / next

- `--until submit` sends the employer form for each Tailored card. Dover and Recruitee are supported. Applied is only after the site accepts the form. A captcha stop stays in Tailored. An account wall goes to Needs you.
- Scheduled mail does not run until `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, and `GMAIL_REFRESH_TOKEN` are in `.env`. The inbox can still be read from this chat.
- `--until advance` tailors each Found card and attaches the Word resume and Word cover letter, then tries the same submit. If the employer form is not submitted, the card stays in Tailored and a comment names the failed submit step. A failed tailor or file step goes to Needs you.
- Evaluate node (ATS pass / AI-written flag) is in the UI via **Check ATS**; still local heuristics, not a vendor ATS
- Job search prefs (titles, tags, query `"react"`, max 40) are still hardcoded in `web.py`

## Known constraints

- Root venv (`bin/`, `lib/`) is gitignored; do not treat it as app code
- `output/` is gitignored — local job cache and tailored CVs, not source of truth
- **Apply submits Dover and Recruitee forms** after the resume and cover letter exist. It refuses non-remote roles. Submitted is only set when the site accepts the form. Cloudflare or hCaptcha can stop a Chrome run; the card then stays in Tailored.
- `.env` `ANTHROPIC_API_KEY` is accepted by Claude (`claude-haiku-4-5`). Tailor and cover letters can run.
- Glassdoor’s HTTP fetch still gets a Cloudflare challenge. A browser session can load the site: remote + last day for “frontend engineer” returned 2 US listings, saved in `output/glassdoor_jobs.json`. Claude wrote `output/cover_Grafana_Labs.md`. Apply still does not submit the form.
