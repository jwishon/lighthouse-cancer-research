"""Shared logic for the Lighthouse research worker.

Cancer-agnostic by design: the worker's search terms come from the patient
profile (or environment overrides), never from hardcoded disease names. There
is no database and no dashboard here — this is the daily research engine only.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Paths -- everything lives under a data dir you control (gitignored).
DATA_DIR = Path(os.environ.get("LIGHTHOUSE_DATA_DIR", "./data"))
PATIENT_PROFILE_PATH = DATA_DIR / "patient-profile.md"
IDEA_STATION_PATH = DATA_DIR / "idea-station.md"
DIGEST_DIR = DATA_DIR / "digests"
SEEN_SOURCES_PATH = DATA_DIR / "seen_sources.json"


@dataclass
class DigestSummary:
    date: str
    path: Path
    size_bytes: int
    modified: datetime


# Profile + idea station ----------------------------------------------------


def load_patient_profile() -> str:
    if PATIENT_PROFILE_PATH.exists():
        return PATIENT_PROFILE_PATH.read_text(encoding="utf-8")
    return ""


def load_idea_station() -> str:
    if not IDEA_STATION_PATH.exists():
        return ""
    return IDEA_STATION_PATH.read_text(encoding="utf-8")


def _profile_field(profile_text: str, *field_names: str) -> str:
    """Pull a value out of the markdown profile by field label.

    Matches lines like '- **Cancer type:** pancreatic adenocarcinoma',
    tolerant of bold markers and leading bullets. Strips italic guidance
    '*(...)*' and placeholder values like 'TBD'. Returns '' if not found
    or not filled in.
    """
    wanted = [n.lower() for n in field_names]
    for raw in profile_text.splitlines():
        line = raw.strip().lstrip("-").strip()
        line = line.replace("**", "")
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip().lower() not in wanted:
            continue
        value = value.strip()
        # Drop italic guidance text that may follow the value in templates.
        value = re.sub(r"\*\(.*?\)\*", "", value).strip()
        value = value.strip("*").strip()
        if not value or value.upper() in {"TBD", "TODO", "UNKNOWN", "N/A"}:
            return ""
        return value
    return ""


def get_search_condition(profile_text: str | None = None) -> str:
    """The primary disease term every search is scoped to.

    Priority: LIGHTHOUSE_CONDITION env override, then the 'Cancer type' field
    in the profile. This is what makes Lighthouse cancer-agnostic — nothing
    here is hardcoded to a single disease.
    """
    override = os.environ.get("LIGHTHOUSE_CONDITION", "").strip()
    if override:
        return override
    if profile_text is None:
        profile_text = load_patient_profile()
    condition = _profile_field(profile_text, "cancer type", "diagnosis", "condition")
    return condition


def get_search_location(profile_text: str | None = None) -> str:
    """Geography used to scope clinical-trial searches. Optional."""
    override = os.environ.get("LIGHTHOUSE_LOCATION", "").strip()
    if override:
        return override
    if profile_text is None:
        profile_text = load_patient_profile()
    return _profile_field(profile_text, "geography", "city, state", "city/state", "location")


def list_active_idea_topics() -> list[str]:
    topics: list[str] = []
    for line in load_idea_station().splitlines():
        s = line.strip()
        if not s.startswith("- "):
            continue
        body = s[2:].strip()
        low = body.lower()
        if "(empty)" in low or "(none)" in low or "(example)" in low or not body:
            continue
        # Skip italic-only template placeholder lines.
        if body.startswith("*") and body.endswith("*"):
            continue
        topics.append(body)
    return topics


# Digests -------------------------------------------------------------------


def list_digests() -> list[DigestSummary]:
    if not DIGEST_DIR.exists():
        return []
    digests: list[DigestSummary] = []
    for p in DIGEST_DIR.glob("*-digest.md"):
        date = p.stem.replace("-digest", "")
        stat = p.stat()
        digests.append(
            DigestSummary(
                date=date, path=p, size_bytes=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            )
        )
    digests.sort(key=lambda d: d.date, reverse=True)
    return digests


def get_recent_digest_summaries(limit: int = 3) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    for d in list_digests()[:limit]:
        text = d.path.read_text(encoding="utf-8")
        headers = [
            re.sub(r"^#+\s*", "", line).strip()
            for line in text.splitlines() if line.startswith("##")
        ]
        titles = re.findall(r"\*\*([^*\n]{8,150})\*\*", text)[:8]
        summaries.append({
            "date": d.date,
            "headers": " | ".join(headers[:6]),
            "titles": " | ".join(titles),
        })
    return summaries


# Seen sources (dedup memory) ----------------------------------------------


def load_seen_sources() -> dict[str, set[str]]:
    empty = {"pmids": set(), "nct_ids": set(), "dois": set(), "exa_urls": set()}
    if not SEEN_SOURCES_PATH.exists():
        return empty
    try:
        data = json.loads(SEEN_SOURCES_PATH.read_text(encoding="utf-8"))
        return {k: set(data.get(k, [])) for k in empty}
    except Exception:
        return empty


def save_seen_sources(seen: dict[str, set[str]]) -> None:
    SEEN_SOURCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "pmids": sorted(seen.get("pmids", set())),
        "nct_ids": sorted(seen.get("nct_ids", set())),
        "dois": sorted(seen.get("dois", set())),
        "exa_urls": sorted(seen.get("exa_urls", set())),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    SEEN_SOURCES_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")


def filter_unseen(items: list[dict[str, Any]], id_field: str, seen_set: set[str]) -> list[dict[str, Any]]:
    return [it for it in items if it.get(id_field) and it[id_field] not in seen_set]


# URL fetch (for optional focus-URL analysis) -------------------------------


def is_url(text: str) -> bool:
    return bool(re.match(r"^https?://", text.strip(), re.IGNORECASE))


def fetch_url_text(url: str, max_chars: int = 30000) -> str:
    from curl_cffi import requests as cffi_requests
    resp = cffi_requests.get(url, timeout=30, impersonate="chrome120")
    html = resp.text
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


# Digest cleanup ------------------------------------------------------------

_JSON_TAIL_RE = re.compile(r"```json\s*\n(\{.*?\})\s*\n```", re.DOTALL)


def strip_json_tail(digest_response: str) -> str:
    """Remove any trailing JSON code block so the emailed digest stays clean."""
    stripped = _JSON_TAIL_RE.sub("", digest_response)
    stripped = re.sub(r"\n---+\s*\n?\s*$", "\n", stripped)
    return stripped.rstrip() + "\n"
