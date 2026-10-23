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

## 2026-10-23 — Agent setup answer stays inside the real files

Choice: When a form asks what is in the agent setup, name the always-on project rule, `docs/STATUS.md`, and `docs/DECISIONS.md`. Design rules are the trading UI's shared primitives, strict TypeScript, and feature modules. A diff is read, the unit tests pass, and on that UI Jest and the typecheck run before merge.

Why: That is the setup on this machine and on the CV. A design-token file is not part of it.

## 2026-10-23 — Trading UI is the brief-to-production answer

Choice: When a form asks for one frontend taken from a brief to production, and what belonged to you, the team, and the agents, use the Identity Global trading UI. Cursor and Claude review and refactor. They do not own the screen.

Why: That is the frontend on the CV. The agents line stays inside the daily-use fact already written there.

## 2026-10-23 — Remember jobs that were already checked

Choice: A role with a location limit, a skill far outside the CV, pay that is too low, or a posting that is gone is archived off Needs you. Its URL is stored in `data/checked_jobs.md`. The next board run skips those URLs.

Why: Archiving a card alone lets the next fetch add the same role again.

## 2026-10-23 — Each scheduled run tailors, writes the letter, and applies

Choice: The 9:00 and 15:00 launchd job runs `--until daily`. For each new Found card it rewrites the CV summary around skills already on the CV, writes a short cover letter from those facts, and submits the form when the site allows it. Claude is not called.

Why: The schedule has to apply on its own, and the CV should stay on this machine.

## 2026-10-23 — Wider search, and skip Claude for now

Choice: A boards fetch reads up to 150 listings from each source, five Himalayas pages, and more Wellfound, Remote OK, and Remotive queries. Backend, mobile, and React Native titles are left off even when the title also says full-stack. The scheduled job stops after Found cards. It does not send the CV to Claude. A resume or cover letter for an application is written here.

Why: One new card a day is not enough for 10 applications, and the CV should not be sent out to be rewritten.

## 2026-10-23 — Run the morning job at 9:00

Choice: launchd starts the daily run at 9:00 and 15:00 London time.

Why: The morning pass should start an hour earlier. The afternoon pass stays at 15:00.

## 2026-10-22 — Keep only fully remote roles that hire from anywhere

Choice: A listing is kept only when it is fully remote and does not limit the country, region, or timezone. Europe-only, Bulgaria-only, and a fixed country list are left off, including a list that names Bulgaria. Hybrid and partly remote roles stay off.

Why: Roles that are remote inside one region still require being there. The search is for work that can be done from anywhere.

Rejected: Treating Europe or Bulgaria as an open location.

## 2026-10-21 — Save open-question answers on the card

Choice: Written answers for the usual application questions live in `data/form_answers.md` and are copied onto the Trello card as a comment before the form is sent. They are written from the CV, in the first person.

Why: The same questions come back on later forms, and the card should show what was asked and what was answered.

## 2026-10-21 — Skip a board that does not answer

Choice: Each source in a fetch has 150 seconds. If it is still waiting, that source is skipped and the run continues.

Why: One site held the connection open and the 15:00 job could not finish the new board list.

## 2026-10-21 — Fetch Eastern Europe, then remote boards, then general boards

Choice: The default `boards` fetch adds DEV.bg, Jobs.bg, JobTiger, Rabota.bg, No Fluff Jobs, Just Join IT, Bulldogjob, and Djinni first, then We Work Remotely, 4 Day Week, JustRemote, Working Nomads, EU Remote Jobs, and Dynamite Jobs, then LinkedIn, Indeed, Welcome to the Jungle, Arc, Y Combinator, Hacker News, Landing.jobs, and Relocate.me. Bulgaria and Sofia count as an open location. A public page that answers with a bot check, or that does not include listings, is skipped for that run.

Why: The search should see Bulgarian and Central European tech boards before the international ones. Roles that are remote inside Bulgaria are roles he can take.

## 2026-10-21 — Skip closed country lists and unpaid roles

Choice: A role is left off the board when it is unpaid or volunteer, or when its locations are a fixed country list that does not include Bulgaria or Europe. Current salary and expected salary are both 85000 when a form requires a number. The Wellfound password lives only in `.env`.

Why: Spotter Labs only hires in countries other than Bulgaria, and Solution Community is unpaid. Those are not applications.

---

## 2026-10-21 — Version every change and push it

Choice: `VERSION` is the app version. Each finished change bumps it, commits, tags `vX.Y.Z`, and pushes to origin. The current snapshot is v0.4.0. Earlier commits are tagged v0.1.0, v0.2.0, and v0.3.0. `.env` and PDFs stay untracked.

Why: A later request to undo a change needs a named version, not a guess about which commit that was.

---

## 2026-10-21 — Apply to every good match

Choice: A daily run scores every listing it fetched. A good match is a score above 50%. Every new good match is added and the apply step runs for each of them. US-only, country-locked, non-remote, and non-frontend roles stay off the board, as do URLs already on the board. One role per company. The same run writes `output/reports/latest.md`, and the local UI shows that file.

Why: The five-card cap and the top-40 ranking cutoff were dropping roles that had already been found and scored well.

Rejected: Keeping a daily maximum.

---

## 2026-10-21 — Run the job every day at 10:00 and 15:00 London

Choice: `--until daily` fetches remote frontend and full-stack roles, adds every new match above 50%, tailors and submits the ones it can, then reads mail. launchd starts that command every day at 10:00 and 15:00. The Mac clock is Europe/London, so those hours are London time. Newsletters are ignored. A rejection moves the matching card to Rejected. An interview invite gets a short reply. A real question is left on the card as Needs you until it can be answered from the facts already given. The scheduled mail step waits until Gmail client credentials are stored in `.env`, because the chat Gmail sign-in cannot run from launchd.

Why: The search, the applications, and the inbox should happen twice a day without a manual start, including weekends. The Mac has to be awake.

Rejected: A Cursor cloud automation. The Trello token, the resume, and the Chrome apply session live on this Mac.

---

## 2026-10-19 — Submit the employer form, then move the card

Choice: `--until submit` opens the employer form for each Tailored card. Dover gets the name, email, phone, LinkedIn, a text PDF of the Word resume, and the cover letter. Recruitee also selects Sofia, Bulgaria and attaches the cover letter file. The card moves to Applied only after the site accepts the form. A captcha that does not finish leaves the card in Tailored and names that step. A site that requires a new account moves the card to Needs you.

Why: A saved resume and letter are not an application. Himalayas postings redirect to Dover or Recruitee, and those forms can be sent.

Rejected: Marking Applied when the form was only prepared.

---

## 2026-10-19 — Phone is a form answer, and cover letters are Word files

Choice: `+372 5605 7387` is stored as `APPLICANT_PHONE` and copied onto an application record as `form_phone`. Resume text and cover letters omit it. Cover letters are saved as `output/cover_<company>.docx`.

Why: Employer forms ask for a phone number. The resume and the letter should not carry it.

---

## 2026-10-19 — Found cards get a tailored resume, then an apply packet

Choice: `--until advance` tailors the resume, writes the Word cover letter, and attaches both. If the employer form is not submitted, the card stays in Tailored and the comment names that failed step. A tailor or file failure moves the card to Needs you. Applied is only for a form that was actually sent.

Why: A ready packet is not an application. The board should show the last step that finished.

---

## 2026-10-19 — First board run adds the top five matches to Found

Choice: `python -m job_assistant.main --until board` fetches, ranks against the CV, and creates up to five new Trello cards in Found. Crypto-paid roles rank above closer matches. One role per company. US-only roles, country-locked or city-locked roles, non-remote roles, designer titles, and titles outside frontend/full-stack are left off the board. Worldwide and Europe-open roles stay eligible. A URL already on the board is not added again.

Why: The board exists, and the first useful step is filling Found from the current remote search.

---

## 2026-10-19 — Track each application on a Trello board

Choice: A private Trello board named Job Search is the pipeline. Columns, left to right: Needs you, Found, Tailored, Applied, Replied, Interview, Rejected. `TRELLO_API_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_ID`, and `TRELLO_LISTS` live in `.env`.

Why: Each step needs its own column, and anything unclear needs a place you can see. Trello lists are those columns. Jira rejected the API token on a new site.

Rejected: Jira Cloud for the same board.

---

## 2026-10-19 — Apply only remote jobs, and do not mark a packet as sent

Choice: Fetch and the job board keep fully remote roles. Hybrid and on-site listings are dropped. Apply refuses a non-remote job. A saved letter and Word resume are status `ready`, not submitted. The UI chip says Ready. Submitted is reserved for a completed employer form.

Why: Office roles were reachable from the same list, and Apply stamped Applied after only writing a local file.

Rejected: Treating “remote” in a hybrid title as eligible.

---

## 2026-10-19 — Apply across Glassdoor and the other boards

Choice: Default source is `boards`. One fetch merges Himalayas (worldwide), Wellfound, Remote OK, Remotive, and Glassdoor remote jobs from the last day. A blocked Glassdoor response does not fail the other boards. Rank still uses the CV, then the top matches get a cover letter and an apply packet.

Why: Applications should start from the current remote listings, not only Himalayas. Glassdoor has no public jobs API.

Rejected: Stopping the whole fetch when Glassdoor returns a bot check. Auto-submitting employer forms.

---

## 2026-08-19 — Cover letter is its own Claude node

Choice: `write_cover_letter` is a graph node (and `POST /api/cover`). One Haiku structured call from the CV + JD. `apply_job` only records the letter and opens the posting. No template letter.

Why: Apply was a static paragraph. A dedicated node matches optimize (opt-in LLM, truthful, per listing) and can stop at `--until cover`.

Rejected: Keeping the hardcoded apply_job template as the writer.

---

## 2026-08-19 — Apply node opens the posting; does not auto-submit

Choice: `apply_job` records the Claude cover letter, writes `output/applications.json`, and the UI opens the listing URL. You still paste/upload the Word CV on the employer site.

Why: Himalayas/Greenhouse have no public apply API. Auto-filling third-party forms is brittle and the wrong layer for this tool.

Rejected: Headless browser submit.

## 2026-08-19 — CV: Option A only, LLM via Job Assistant

Choice: Rewrite `data/alireza_tahani_cv.md` with truthful structured-data bullets, Cursor/Claude as daily tools, and a Relevant Projects entry for this LangGraph + Claude API app. Current employers on the CV: SAP (Germany) / Identity Global (UK); Fixefy.io (not IranTalent).

Why: The RCM JD needs LLM keywords. Inventing production LLM, HIPAA, or MySQL/Redis at SAP / Identity Global would fail an interview.

Rejected: Option B production-LLM bullets under a trading-platform role; healthcare-claims similes.

## 2026-08-19 — Cheap Haiku, one tailor request

Choice: Default `ANTHROPIC_MODEL=claude-haiku-4-5`. Optimize is a single structured call (tailor + human voice). Leftover clichés are stripped locally. No second humanize request.

Why: Sonnet + a follow-up pass was ~5¢ per job. Haiku is the cheap tier; one round-trip is enough.

## 2026-08-19 — Anthropic for CV tailor

Choice: `get_llm()` uses `ChatAnthropic` with `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL`.

Why: OpenAI account was unbilled. Tailor still needs a chat model; Anthropic is the wired provider now.

Rejected: Keeping OpenAI as the optimize backend.

## 2026-08-18 — No personal location or phone on the CV

Choice: Contact header is email only. Strip location/phone from the source CV, Word downloads, and any tailored output.

Why: Keep Tehran/phone off applications. Employer cities in experience stay only where they belong.

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
