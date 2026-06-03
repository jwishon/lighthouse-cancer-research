# Research sources

Lighthouse pulls from a core set of sources that work for **any** cancer type, plus optional "type packs" you can add for your specific diagnosis. You don't have to touch this file to get started — it's here so you understand where findings come from and can tune it later.

## Core sources (work for every cancer type)

These are queried on every run, scoped by your profile.

- **PubMed** — peer-reviewed studies, reviews, case reports.
  NCBI E-utilities API, free. An optional free API key raises rate limits.
- **ClinicalTrials.gov** — actively recruiting trials, eligibility criteria, locations.
  API v2, free, no key required.
- **ASCO / ESMO conference abstracts** — where the freshest data often appears, months before publication.
- **Cochrane Reviews** — high-quality evidence syntheses, useful for supportive care and lifestyle questions.

## Optional type packs

When you set up your profile, Lighthouse can suggest extra sources tuned to your cancer type. These are optional and you can edit them freely:

- **The matching NCCN guideline** for your cancer (reference, usually login-gated).
- **A disease-specific advocacy organization** (for example, a foundation focused on your cancer type) — often the best plain-language explanations and trial-finder tools.
- **A patient community** for your diagnosis (read-only, summarized carefully — never copy personal stories or identifying details).

> The setup step proposes a starter type pack based on the cancer type in your profile. Nothing here is hardcoded to one disease — it adapts to what you enter.

## How findings are handled

- Every finding cites its **source and date**. No exceptions.
- Primary sources are preferred over secondary; secondary sources are flagged as such.
- Findings are ranked on two separate axes so weak evidence isn't dressed up as strong:
  - **Evidence level** — how mature the research is (preprint → early trial → large trial → guideline).
  - **Study quality** — how well the study was done.
- Preprints and unpublished abstracts are always marked low-confidence until peer review.
- When findings conflict, Lighthouse shows you both and the evidence behind each, rather than picking a winner.

## Adding or removing sources

Lighthouse is built so sources are configuration, not code. To add a source, point it at an API or feed and tell the worker how to query it. Keep these rules:

- **Respect each source's terms of use and rate limits.**
- **Never scrape personal health information** from patient communities. Summarize general findings only; do not reproduce individuals' stories or identifying details.
- **Always keep the link** back to the original so a human can verify it.
