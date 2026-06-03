# AGENTS.md — instructions for AI assistants setting up Lighthouse

> This file is read by AI coding tools (Claude Cowork, Claude Code, Cursor, VS Code AI extensions, and others). If you are an AI assistant helping a human stand up Lighthouse, follow this. If you are a human, you can read it too — it's just the setup, written for a helper.

## What Lighthouse is

A daily research tool for one cancer patient. It reads a profile, searches medical databases, uses an AI model to summarize and rank findings, and emails a digest. The person you're helping is usually a caregiver, not a developer. Be patient, explain in plain language, and never rush them.

## Your job

Help the user get Lighthouse running for their situation. Work through these steps with them, confirming as you go.

### 1. Set expectations and boundaries first

Before anything else, make sure the user understands — and you must hold to — these rules:

- **This is not medical advice.** Never tell the user what treatment to choose, never predict prognosis or odds, never interpret results as a clinician would. Everything Lighthouse produces is "to discuss with the care team."
- **Their data stays theirs.** Keep patient information on their machine. Do not commit the profile, the idea station, or any digest to a public repository. Do not paste real patient details into any external service beyond what the configured research and AI APIs require.
- **No direct identifiers.** Guide them to use a first name or no name — never a full name, address, or medical record number in the profile.

### 2. Build the profile

- Create a `data/` folder and copy `config/patient-profile.template.md` to `data/patient-profile.md`.
- Interview the user gently to fill it in: cancer type (as specific as the care team has been — subtype matters), stage, date of diagnosis, biomarkers/molecular results if they have them, geography for trial eligibility, current and prior treatment, trial willingness, travel willingness, interest in lifestyle/integrative evidence.
- If they don't know a field, leave it blank and tell them it's worth asking the care team. Don't guess medical facts.

### 3. Build the idea station

- Copy `config/idea-station.template.md` to `data/idea-station.md`.
- Ask what questions they most want answered. Seed a few based on their profile (e.g., recruiting trials near them for this diagnosis and stage).

### 4. Suggest a source type pack

- The core sources (PubMed, ClinicalTrials.gov, ASCO/ESMO, Cochrane) work for any cancer and are already on.
- Based on the cancer type in the profile, suggest an optional type pack: the matching NCCN guideline, a disease-specific advocacy organization, and a patient community for that diagnosis. See `docs/research-sources.md`. Confirm before adding.

### 5. Configure keys and delivery

- Copy `config/config.example.env` to `config/.env`.
- Help the user add their AI model API key, an optional NCBI key, and email-sending settings. If they want to keep all text local, set up a local model instead and tell them the trade-off (slower, less polished, fully private).
- Never print secret keys back in plain text in a shared log. Confirm `config/.env` and the `data/` folder are listed in `.gitignore`.

### 6. Do a test run

- Run the worker once (`cd worker && python main.py`). Read the digest **with** the user.
- Check that every finding has a working source link, that nothing reads as medical advice, and that the AI summaries match the underlying sources. If a summary overstates the evidence, flag it.

### 7. Schedule it

- Once the user is happy with a test digest, set up a daily run (cron, Task Scheduler, or their host's scheduler).
- Show them how to update the profile and idea station later — that's how the research stays relevant.

## Things you must not do

- Do not give medical advice or let the output read as advice.
- Do not predict outcomes, survival, or odds.
- Do not commit patient data, profiles, digests, or secrets to any remote repository.
- Do not scrape or reproduce identifiable personal stories from patient communities.
- Do not skip the disclaimer conversation to save time.

## If something's missing

The research worker code lives in the `worker/` folder (added when the engine is ported in). If it isn't present yet, tell the user the documentation scaffold is ready but the engine still needs t