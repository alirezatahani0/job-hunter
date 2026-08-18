# Job Assistant (LangGraph)

Python LangGraph workflow that finds a remote job, ranks it, tailors your CV to the JD, scores the result (relevance / readability / ATS / AI-flag), and prints the JD link with the updated resume.

## Graph

```
START
  → fetch_jobs      # Himalayas (worldwide location + all hiring timezones)
  → sort_jobs       # rank by title, salary, location, tags
  → optimize_cv     # OpenAI tailored rewrite
  → evaluate_cv     # JD fit, readability, format, ATS, AI-detect
  → print_output    # console + output/*.md
END
```

## Setup

```bash
# from project root (venv already present)
source bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

## Run (Himalayas fetch → state)

```bash
export PYTHONPATH=src
python -m job_assistant.main --fetch-only --source himalayas
# jobs land in graph state + output/himalayas_jobs.json
```

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

- Default `--source himalayas` uses the [Himalayas Jobs API](https://himalayas.app/docs/remote-jobs-api) and keeps only worldwide / all-timezone roles.
- Link back / attribute the boards if you redistribute listings (their API ToS).
- Outputs land in `output/application_*.md` with JD URL + evaluation + updated resume.
