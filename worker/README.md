# Lighthouse worker

The daily research engine. It reads a patient profile, searches medical
literature and trial registries scoped to that cancer, asks an AI model to
summarize and rank what it finds, writes a markdown digest, and emails it.

This is the only code you need to run Lighthouse. There's no database and no
web app — just two Python files and a daily schedule.

## Files

- `main.py` — the worker: search, synthesize, write digest, email.
- `core.py` — profile parsing, dedup memory, digest helpers.
- `requirements.txt` — Python dependencies.
- `Dockerfile` — optional container image for scheduled runs.

## What it reads and writes

```
data/
  patient-profile.md     # you fill this in (from config/patient-profile.template.md)
  idea-station.md        # optional questions to chase (from the template)
  digests/               # written here: YYYY-MM-DD-digest.md
  seen_sources.json      # dedup memory, so you don't get repeats
config/
  .env                   # your API keys and email settings
```

Everything under `data/` and `config/.env` is gitignored — patient information
never enters version control.

## Run it (local)

From the repository root:

```bash
# 1. Install dependencies (a virtualenv is recommended)
pip install -r worker/requirements.txt

# 2. Set up your data and config
mkdir -p data
cp config/patient-profile.template.md data/patient-profile.md
cp config/idea-station.template.md   data/idea-station.md
cp config/config.example.env         config/.env
# ...then edit data/patient-profile.md and config/.env

# 3. Run one digest
cd worker && python main.py
```

The first run writes a digest to `data/digests/` and emails it if email is
configured. Read it before you automate.

### Optional: analyze a specific page

Pass a URL to fold a specific article or press release into the digest with a
credibility check:

```bash
cd worker && python main.py "https://example.com/some-article"
```

## Schedule it (daily)

Pick whatever your machine offers:

- **Linux/macOS cron** — e.g. run at 6am daily:
  ```
  0 6 * * * cd /path/to/lighthouse/worker && /path/to/python main.py >> /path/to/lighthouse/data/worker.log 2>&1
  ```
- **Windows Task Scheduler** — point a daily task at `python main.py` in the `worker` folder.
- **Docker** — build with `docker build -t lighthouse worker/`, then run on a schedule with `data/` and `config/.env` mounted in.

## Configuration

All settings live in `config/.env` (copied from `config/config.example.env`).
The only required value is `ANTHROPIC_API_KEY`. The cancer type comes from the
profile automatically; everything else has a sensible default.

## Reminder

Lighthouse is a research aid, not medical advice. Every digest is something to
bring to a qualified care team. See `../DISCLAIMER.md`.
