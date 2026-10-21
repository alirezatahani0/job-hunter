# Job Assistant (LangGraph)

Python LangGraph workflow that finds a remote job, ranks it, tailors your CV to the JD, scores the result (relevance / readability / ATS / AI-flag), and prints the JD link with the updated resume.

## Graph

```
START
  → fetch_jobs      # boards: Glassdoor + Himalayas + Wellfound + Remote OK + Remotive
  → sort_jobs       # rank against CV skills + role fit
  → optimize_cv     # JD-tailored rewrite, then humanize for ATS
  → evaluate_cv     # local ATS / keyword check
  → write_cover_letter  # Claude letter from CV + JD
  → apply_job       # save packet + apply URL (you submit)
  → print_output    # console + output/*.md
END
```

## Setup

```bash
# from project root (venv already present)
source bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
```

## Run (fetch + rank against CV)

```bash
export PYTHONPATH=src
python -m job_assistant.main --until sort --source boards
# tailored resume: output/optimized_cv.md
```

Open a job in the UI and click **Tailor resume to this JD** or **Write cover letter**.

Only listings whose **Location requirements** are Worldwide / all countries **and** **Hiring timezones** are unrestricted / all timezones are kept.

Full pipeline:

```bash
python -m job_assistant.main --source himalayas
```

Source options: `himalayas` (default), `wellfound`, `auto`, `remoteok`, `remotive`.

## Frontend

```bash
export PYTHONPATH=src
python -m job_assistant.web
# open http://127.0.0.1:8765
```

Reads `output/himalayas_jobs.json` and can refresh from Himalayas in the UI.

## Notes

- Default `--source boards` pulls Glassdoor (last day, remote), Himalayas worldwide roles, Wellfound, Remote OK, and Remotive, then ranks them against the CV.
- Link back / attribute the boards if you redistribute listings (their API ToS).
- Outputs land in `output/application_*.md` with JD URL + evaluation + updated resume.
