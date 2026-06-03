# Setup

Lighthouse is two text files (a profile and an idea list) plus a small daily job that reads them, searches medical databases, and emails you a digest. You can set it up three ways. Pick one.

> Before you add any real information, read [DISCLAIMER.md](DISCLAIMER.md). Short version: this is a research aid, not medical advice, and your data should stay on a machine you control.

---

## What you need first

- **An AI model API key.** The default uses Anthropic's Claude. You can swap in another provider — see [Swapping the AI model](#swapping-the-ai-model).
- **An email-sending method** for the digest (any SMTP account, or a service like Resend). Optional if you only want to read digests as files.
- **Somewhere to run a daily job** — your own computer, a home server, or a small cloud host.
- *(Optional)* a free **NCBI/PubMed API key** to raise rate limits.

You do **not** need a paid PubMed or ClinicalTrials.gov account — those are free and open.

---

## Path A — with an AI assistant

*The easiest path, and the one we used. No coding required.*

1. Download or clone this folder onto your computer.
2. Open it in an AI coding tool — **Claude Cowork**, **Claude Code**, **Cursor**, or **VS Code** with an AI assistant.
3. Tell the assistant: *"Read AGENTS.md and help me set up Lighthouse."*
4. The assistant will read [`AGENTS.md`](AGENTS.md) and walk you through it: it asks about the diagnosis and fills in your profile, helps you put your API keys in the right place, suggests sources for your specific cancer type, and gets the daily job scheduled.
5. Confirm the first digest looks right before you let it run on its own.

Any of those tools works because they all read the same `AGENTS.md` instructions file. Use whichever you already have.

---

## Path B — by hand

*For people comfortable editing files and running a command.*

1. Create a `data/` folder and copy the templates into it:
   - `config/patient-profile.template.md` → `data/patient-profile.md`
   - `config/idea-station.template.md` → `data/idea-station.md`
2. Fill in `data/patient-profile.md` (cancer type, stage, biomarkers, geography). First name or no name — no direct identifiers.
3. Copy `config/config.example.env` → `config/.env` and add your API keys and email settings.
4. Install dependencies and run the worker once to test. Full commands are in [`worker/README.md`](worker/README.md).
5. Schedule it to run daily (cron, Task Scheduler, or your host's scheduler — see the worker README).

The whole `data/` folder and `config/.env` are excluded from version control by [`.gitignore`](.gitignore) so patient information is never committed. Leave that in place.

---

## Path C — one run first

Not ready to automate? Fill in the profile, run the worker once, and read the digest it produces. If it's useful, set up the daily schedule from Path A or B. If it's not, you've lost ten minutes, not a weekend.

---

## Swapping the AI model

The default configuration calls Anthropic's Claude to summarize and rank findings. To use a different provider, change the model settings in `config/.env` and the model client in the worker. If you'd rather keep all text on your own hardware, you can point it at a locally hosted model — slower and a bit less polished, but nothing leaves your machine.

## Keeping it healthy

- **Update the profile** whenever something changes — a new scan, a new treatment line, a new biomarker. The research follows the profile.
- **Prune the idea station** so it reflects what you actually want chased now.
- **Check the source links.** If a finding matters, open the original and confirm it before raising it with the care team.

## Trouble

- *No findings?* The profile may be too narrow, or the day's literature genuinely had nothing new. Broaden the profile or check the idea station.
- *Digest never arrived?* Check the email settings in `.env` and the job's logs.
- *AI summaries look off?* Open the linked source — the model can mi