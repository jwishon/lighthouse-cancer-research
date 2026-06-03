"""Lighthouse — daily cancer-research worker.

Reads a patient profile, searches medical literature and trial registries
scoped to whatever cancer the profile describes, asks an AI model to summarize
and rank findings, writes a markdown digest, and emails it.

Not medical advice. See DISCLAIMER.md. Run on a daily schedule.
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx
from anthropic import Anthropic
from curl_cffi import requests as cffi_requests
from dotenv import load_dotenv

import core

load_dotenv()
load_dotenv(dotenv_path="config/.env")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "7"))
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
CONTACT_EMAIL = os.environ.get("LIGHTHOUSE_CONTACT_EMAIL", "anonymous@example.com")
MODEL_SYNTHESIS = os.environ.get("LIGHTHOUSE_MODEL_SYNTHESIS", "claude-sonnet-4-6")
DIGEST_MAX_ITEMS = int(os.environ.get("DIGEST_MAX_ITEMS", "12"))

# Email delivery
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
DIGEST_FROM = os.environ.get("DIGEST_FROM", "")
DIGEST_TO = os.environ.get("DIGEST_TO", "")

HTTP_HEADERS = {
    "User-Agent": "Lighthouse/1.0 (open-source cancer-research aid; contact: " + CONTACT_EMAIL + ")",
    "Accept": "application/json",
}

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CTGOV_BASE = "https://clinicaltrials.gov/api/v2/studies"
EUROPE_PMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EXA_BASE = "https://api.exa.ai/search"


def log(msg: str) -> None:
    print("[lighthouse] " + msg)


# --- Sources ---------------------------------------------------------------


def search_preprints(query: str, days_back: int = 14, limit: int = 25) -> list[dict[str, Any]]:
    """Europe PMC preprints (bioRxiv, medRxiv, etc.) — new findings often drop
    here weeks before peer review. Always flagged low-confidence downstream."""
    today = datetime.now(timezone.utc).date()
    mindate = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    maxdate = today.strftime("%Y-%m-%d")
    q = query + " SRC:PPR FIRST_PDATE:[" + mindate + " TO " + maxdate + "]"
    try:
        resp = httpx.get(
            EUROPE_PMC_BASE,
            params={"query": q, "format": "json", "pageSize": str(limit), "resultType": "core"},
            headers=HTTP_HEADERS, timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print("[lighthouse] preprint fetch failed: " + str(exc), file=sys.stderr)
        return []
    results: list[dict[str, Any]] = []
    for r in data.get("resultList", {}).get("result", []):
        doi = (r.get("doi") or "").strip()
        ppr_id = (r.get("id") or "").strip()
        results.append({
            "doi": doi or ppr_id,
            "title": (r.get("title") or "").strip(),
            "abstract": (r.get("abstractText") or "").strip()[:3000],
            "authors": (r.get("authorString") or "")[:300],
            "preprint_server": (r.get("bookOrReportDetails", {}) or {}).get("publisher", "") or "preprint",
            "year": (r.get("pubYear") or "").strip(),
            "url": ("https://doi.org/" + doi) if doi else ("https://europepmc.org/article/PPR/" + ppr_id),
        })
    return results


def search_exa(query: str, days_back: int = 14, limit: int = 8) -> list[dict[str, Any]]:
    """Optional broad web/scholarly search via Exa (conferences, news, press
    releases). Best-effort: returns [] if no key is set or on any error."""
    if not EXA_API_KEY:
        return []
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    body = {
        "query": query,
        "numResults": limit,
        "type": "auto",
        "startPublishedDate": start + "T00:00:00.000Z",
        "endPublishedDate": end + "T23:59:59.999Z",
        "contents": {"text": {"maxCharacters": 2000}},
    }
    try:
        resp = httpx.post(
            EXA_BASE,
            headers={**HTTP_HEADERS, "x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
            json=body, timeout=45.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print("[lighthouse] exa fetch failed: " + str(exc), file=sys.stderr)
        return []
    results: list[dict[str, Any]] = []
    for r in data.get("results", []):
        url = (r.get("url") or "").strip()
        if not url:
            continue
        results.append({
            "url": url,
            "title": (r.get("title") or "").strip(),
            "published": (r.get("publishedDate") or "").strip()[:10],
            "author": (r.get("author") or "").strip()[:200],
            "text": (r.get("text") or "").strip()[:2000],
            "source": "exa",
        })
    return results


def search_pubmed(query: str, days_back: int = 7, limit: int = 25) -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    mindate = (today - timedelta(days=days_back)).strftime("%Y/%m/%d")
    maxdate = today.strftime("%Y/%m/%d")
    params = {"db": "pubmed", "term": query, "retmode": "json",
              "retmax": str(limit), "sort": "date", "datetype": "pdat",
              "mindate": mindate, "maxdate": maxdate}
    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    if api_key:
        params["api_key"] = api_key
    search_resp = httpx.get(EUTILS_BASE + "/esearch.fcgi", params=params,
                            headers=HTTP_HEADERS, timeout=30.0)
    search_resp.raise_for_status()
    pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    if not pmids:
        return []
    fetch_params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
    if api_key:
        fetch_params["api_key"] = api_key
    fetch_resp = httpx.get(EUTILS_BASE + "/efetch.fcgi", params=fetch_params,
                           headers=HTTP_HEADERS, timeout=60.0)
    fetch_resp.raise_for_status()
    return _parse_pubmed_xml(fetch_resp.text)


def _parse_pubmed_xml(xml_text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    root = ET.fromstring(xml_text)
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        title_el = article.find(".//ArticleTitle")
        journal_el = article.find(".//Journal/Title")
        year_el = article.find(".//PubDate/Year")
        if year_el is None:
            year_el = article.find(".//PubDate/MedlineDate")
        abstract_parts = [(el.text or "") for el in article.findall(".//Abstract/AbstractText")]
        abstract = " ".join(p.strip() for p in abstract_parts if p).strip()
        pmid = pmid_el.text if pmid_el is not None else ""
        results.append({
            "pmid": pmid,
            "title": (title_el.text if title_el is not None else "").strip(),
            "abstract": abstract,
            "journal": (journal_el.text if journal_el is not None else "").strip(),
            "year": (year_el.text if year_el is not None else "").strip(),
            "url": ("https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/") if pmid else "",
        })
    return results


def search_clinical_trials(condition: str, location: str | None = None,
                           status: str = "RECRUITING", limit: int = 25) -> list[dict[str, Any]]:
    params: dict[str, str] = {
        "query.cond": condition, "filter.overallStatus": status,
        "pageSize": str(limit), "format": "json",
    }
    if location:
        params["query.locn"] = location
    resp = cffi_requests.get(CTGOV_BASE, params=params, headers=HTTP_HEADERS,
                             timeout=30, impersonate="chrome120")
    studies = resp.json().get("studies", [])
    results: list[dict[str, Any]] = []
    for s in studies:
        protocol = s.get("protocolSection", {})
        ident = protocol.get("identificationModule", {})
        status_mod = protocol.get("statusModule", {})
        cond_mod = protocol.get("conditionsModule", {})
        design_mod = protocol.get("designModule", {})
        elig_mod = protocol.get("eligibilityModule", {})
        contacts_mod = protocol.get("contactsLocationsModule", {})
        nct_id = ident.get("nctId", "")
        locations = [
            (loc.get("city", "") + ", " + loc.get("state", "") + ", " + loc.get("country", ""))
            for loc in contacts_mod.get("locations", [])[:5]
        ]
        results.append({
            "nct_id": nct_id,
            "title": ident.get("briefTitle", ""),
            "status": status_mod.get("overallStatus", ""),
            "conditions": cond_mod.get("conditions", []),
            "phase": design_mod.get("phases", []),
            "eligibility_summary": (elig_mod.get("eligibilityCriteria", "") or "")[:1000],
            "locations": locations,
            "url": ("https://clinicaltrials.gov/study/" + nct_id) if nct_id else "",
        })
    return results


# --- Synthesis -------------------------------------------------------------

SYSTEM_PROMPT = """You are a research assistant for a family supporting a loved one with cancer. Your job is to read raw research findings and produce a clear, useful daily digest.

Guidelines:
- Rank by relevance to the patient profile, then by novelty.
- Use plain English. No medical jargon without explanation.
- For each finding, include: a one-line summary, why it matters for THIS patient specifically, the evidence level, and a direct link.
- Flag findings that suggest specific questions to ask the care team.
- NEVER frame findings as medical advice. Frame as "discuss with the care team."
- If nothing significant came back, say so. Do not pad.
- BUILD ON prior digests. Don't repeat findings already covered. Focus on what's NEW.

EVIDENCE — every finding gets BOTH axes (they answer different questions):

evidence_level = trial maturity (where in the development pipeline):
- preclinical: cells/animals, mechanism work
- early-trial: Phase 1 or Phase 2
- late-trial: Phase 3 or pivotal trial
- established: standard of care / guideline-supported

quality_grade = GRADE-style study quality (how strong is the evidence behind THIS specific result):
- HIGH: multiple Phase 3 RCTs, systematic reviews/meta-analyses, established guideline
- MODERATE: single Phase 3 RCT, multiple Phase 2 trials, strong observational evidence
- LOW: Phase 1/2, case series, retrospective single-center, expert opinion
- VERY_LOW: preclinical, preprints awaiting peer review, conference abstracts, anecdotal/community signals
Be honest and conservative. Preprints are ALWAYS VERY_LOW until peer-reviewed. A Phase 3 preprint is late-trial + VERY_LOW; the same trial post-publication is late-trial + HIGH.

CONTRADICTORY EVIDENCE — when findings conflict (one source supports X, another contradicts):
- Do NOT pick one and silently drop the other.
- Surface the conflict explicitly, e.g. "Conflicts with prior finding X — recent paper claims Y, but [methodology difference]. Worth asking the care team to weigh in."
- This is more useful than false confidence.

PREPRINT vs PEER-REVIEWED — clearly mark preprints. They are interesting signal but unvetted. Tag them VERY_LOW until peer-reviewed.

OUTPUT — a clean markdown digest only. For each question you raise for the care team, add a one-sentence plain-English explanation of any medical term in it, written for a smart non-clinician. Do not output JSON or code blocks. Do not give medical advice or predict outcomes."""


def synthesize_findings(profile: str, ideas: str, condition: str,
                        pubmed_results: list[dict[str, Any]],
                        trial_results: list[dict[str, Any]],
                        preprint_results: list[dict[str, Any]] | None = None,
                        exa_results: list[dict[str, Any]] | None = None,
                        recent_digests: list[dict[str, str]] | None = None,
                        url_context: str | None = None,
                        url_source: str | None = None) -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    recent_section = ""
    if recent_digests:
        recent_section = "\n# Recent digests (already covered — build on, don't repeat)\n\n"
        for r in recent_digests:
            recent_section += "- **" + r["date"] + "** sections: " + r["headers"] + "\n"
            if r["titles"]:
                recent_section += "  prior titles: " + r["titles"] + "\n"

    url_section = ""
    if url_context:
        url_section = (
            "\n# Web page submitted for analysis (" + (url_source or "") + ")\n\n```\n"
            + url_context[:20000]
            + "\n```\n\nIncorporate insights from this page. Assess credibility, flag claims that conflict with established evidence, and suggest follow-up questions if applicable.\n"
        )

    user_message = (
        "# Patient profile\n\n" + profile + "\n\n"
        + "# Primary condition being researched\n\n" + condition + "\n\n"
        + "# Open questions / topics from the idea station\n\n" + (ideas or "(none)") + "\n"
        + recent_section + url_section
        + "\n# Raw PubMed results (peer-reviewed, JSON, filtered for novelty)\n\n"
        + json.dumps(pubmed_results, indent=2) + "\n\n"
        + "# Raw preprints (Europe PMC — NOT peer-reviewed, JSON)\n\n"
        + json.dumps(preprint_results or [], indent=2) + "\n\n"
        + "# Raw web/scholarly search via Exa (JSON, may be empty)\n\n"
        + json.dumps(exa_results or [], indent=2) + "\n\n"
        + "# Raw ClinicalTrials.gov results (recruiting + active, JSON, filtered)\n\n"
        + json.dumps(trial_results, indent=2) + "\n\n"
        + "Produce a daily research digest in markdown with these sections:\n"
        + "1. Top findings (ranked by relevance — mark each HIGH / MEDIUM / LOW)\n"
        + "2. New trials worth considering\n"
        + "3. Idea-station follow-ups\n"
        + "4. Questions for the care team (each with a plain-English explanation)\n"
        + "5. Skipped (anything considered but rejected, with a one-line reason)\n\n"
        + "Include up to " + str(DIGEST_MAX_ITEMS) + " findings, ranked top first.\n"
    )

    response = client.messages.create(
        model=MODEL_SYNTHESIS, max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


# --- Output + delivery -----------------------------------------------------


def write_digest(digest_markdown: str) -> Path:
    core.DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest_path = core.DIGEST_DIR / (today + "-digest.md")
    digest_path.write_text(digest_markdown, encoding="utf-8")
    return digest_path


def _markdown_to_html(md_text: str) -> str:
    try:
        import markdown as _md
        return _md.markdown(md_text, extensions=["extra", "sane_lists"])
    except Exception:
        # Fall back to preformatted text if markdown isn't installed.
        return "<pre>" + md_text.replace("<", "&lt;").replace(">", "&gt;") + "</pre>"


def send_email(digest_markdown: str) -> None:
    """Email the digest. Skips quietly if email isn't configured — the digest
    is always written to disk regardless."""
    if not (SMTP_HOST and DIGEST_TO and DIGEST_FROM):
        log("Email skipped: SMTP_HOST / DIGEST_FROM / DIGEST_TO not all set. Digest saved to disk only.")
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    msg = EmailMessage()
    msg["Subject"] = "Lighthouse research digest — " + today
    msg["From"] = DIGEST_FROM
    msg["To"] = DIGEST_TO
    disclaimer = ("This is an automated research digest, not medical advice. "
                  "Discuss anything here with the care team before acting. "
                  "Verify each finding at its source link.\n\n")
    msg.set_content(disclaimer + digest_markdown)
    html_body = ("<p style='color:#666;font-size:13px'>" + disclaimer.strip()
                 + "</p><hr>" + _markdown_to_html(digest_markdown))
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        try:
            server.starttls()
            server.ehlo()
        except smtplib.SMTPException:
            pass  # server may not support STARTTLS
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    log("Emailed digest to " + DIGEST_TO)


# --- Main run --------------------------------------------------------------


def run(focus_url: str | None = None) -> None:
    log("Starting daily run at " + datetime.now(timezone.utc).isoformat())

    profile = core.load_patient_profile()
    if not profile:
        raise FileNotFoundError(
            "Patient profile not found at " + str(core.PATIENT_PROFILE_PATH)
            + ". Copy config/patient-profile.template.md there and fill it in."
        )
    ideas = core.load_idea_station()

    condition = core.get_search_condition(profile)
    if not condition:
        raise ValueError(
            "No cancer type found. Fill in the 'Cancer type' field in the profile, "
            "or set LIGHTHOUSE_CONDITION in your .env."
        )
    location = core.get_search_location(profile) or None
    log("Researching condition: '" + condition + "'" + (" near " + location if location else ""))

    seen = core.load_seen_sources()
    log("Memory: " + str(len(seen["pmids"])) + " PMIDs, " + str(len(seen["nct_ids"])) + " NCT IDs previously seen")

    # Broad baseline query, scoped to the patient's condition.
    pubmed_results = search_pubmed(query=condition, days_back=LOOKBACK_DAYS)
    preprint_results = search_preprints(query=condition, days_back=LOOKBACK_DAYS * 2)
    trial_results = search_clinical_trials(condition=condition, location=location, status="RECRUITING")
    trial_results.extend(search_clinical_trials(condition=condition, location=location,
                                                status="ACTIVE_NOT_RECRUITING", limit=10))
    exa_results = search_exa(query=condition + " treatment news clinical advances",
                             days_back=LOOKBACK_DAYS * 2, limit=8)
    log("Broad query: " + str(len(pubmed_results)) + " pubmed, " + str(len(preprint_results))
        + " preprints, " + str(len(trial_results)) + " trials, " + str(len(exa_results)) + " exa")

    # Targeted sub-queries from the idea station, each scoped to the condition.
    active_topics = core.list_active_idea_topics()
    for topic in active_topics[:8]:
        try:
            sub_p = search_pubmed(query=condition + " " + topic, days_back=LOOKBACK_DAYS * 4, limit=15)
            sub_t = search_clinical_trials(condition=condition + " " + topic, location=location, limit=15)
            sub_e = search_exa(query=condition + " " + topic, days_back=LOOKBACK_DAYS * 4, limit=5)
            pubmed_results.extend(sub_p)
            trial_results.extend(sub_t)
            exa_results.extend(sub_e)
            log("  topic '" + topic[:60] + "': +" + str(len(sub_p)) + " pubmed, +"
                + str(len(sub_t)) + " trials, +" + str(len(sub_e)) + " exa")
        except Exception as exc:
            print("[lighthouse]   topic '" + topic[:60] + "' failed: " + str(exc), file=sys.stderr)

    # In-batch dedup.
    seen_p, seen_t, seen_e = set(), set(), set()
    pubmed_results = [p for p in pubmed_results if p.get("pmid") and p["pmid"] not in seen_p and not seen_p.add(p["pmid"])]
    trial_results = [t for t in trial_results if t.get("nct_id") and t["nct_id"] not in seen_t and not seen_t.add(t["nct_id"])]
    exa_results = [e for e in exa_results if e.get("url") and e["url"] not in seen_e and not seen_e.add(e["url"])]

    # Drop anything already covered in a prior run.
    pubmed_new = core.filter_unseen(pubmed_results, "pmid", seen["pmids"])
    trials_new = core.filter_unseen(trial_results, "nct_id", seen["nct_ids"])
    preprints_new = core.filter_unseen(preprint_results, "doi", seen.get("dois", set()))
    exa_new = core.filter_unseen(exa_results, "url", seen.get("exa_urls", set()))
    log("After dedup: " + str(len(pubmed_new)) + " new pubmed, " + str(len(preprints_new))
        + " new preprints, " + str(len(trials_new)) + " new trials, " + str(len(exa_new)) + " new exa")

    recent = core.get_recent_digest_summaries(limit=3)

    url_context = None
    if focus_url:
        try:
            url_context = core.fetch_url_text(focus_url)
            log("Fetched " + str(len(url_context)) + " chars from " + focus_url)
        except Exception as exc:
            print("[lighthouse] URL fetch failed: " + str(exc), file=sys.stderr)

    full_response = synthesize_findings(
        profile=profile, ideas=ideas, condition=condition,
        pubmed_results=pubmed_new, trial_results=trials_new,
        preprint_results=preprints_new, exa_results=exa_new,
        recent_digests=recent, url_context=url_context, url_source=focus_url,
    )

    digest_markdown = core.strip_json_tail(full_response)
    digest_path = write_digest(digest_markdown)
    log("Digest written to " + str(digest_path))

    # Update dedup memory with everything we saw this run.
    for it in pubmed_results:
        if it.get("pmid"):
            seen["pmids"].add(it["pmid"])
    for it in trial_results:
        if it.get("nct_id"):
            seen["nct_ids"].add(it["nct_id"])
    seen.setdefault("dois", set())
    seen.setdefault("exa_urls", set())
    for it in preprint_results:
        if it.get("doi"):
            seen["dois"].add(it["doi"])
    for it in exa_results:
        if it.get("url"):
            seen["exa_urls"].add(it["url"])
    core.save_seen_sources(seen)

    send_email(digest_markdown)
    log("Done.")


if __name__ == "__main__":
    arg_url = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        run(focus_url=arg_url)
    except Exception as exc:
        print("[lighthouse] FAILED: " + str(exc), file=sys.stderr)
        sys.exit(1)
