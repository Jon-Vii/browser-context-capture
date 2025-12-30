#!/usr/bin/env python3
"""
Browser Context Capture

Reads Chrome and Safari browser history and generates daily markdown digests.
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Configuration
OUTPUT_DIR = Path.home() / "memex" / "browser"
CHROME_BASE = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
SAFARI_HISTORY = Path.home() / "Library" / "Safari" / "History.db"
ERROR_LOG = OUTPUT_DIR / ".errors.log"

# URL prefixes to exclude (noise for AI context)
EXCLUDED_PREFIXES = (
    "chrome://",
    "chrome-extension://",
    "edge://",
    "about:",
    "file://",
    "devtools://",
    "favorites://",
    "bookmarks://",
)

# Tracking parameters to strip from URLs
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_source_platform", "utm_creative_format", "utm_marketing_tactic",
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid",
    "msclkid", "twclid", "ttclid", "li_fat_id",
    "mc_eid", "mc_cid",
    "ref", "_ref", "ref_", "referer", "referrer",
    "source", "_source",
    "igshid", "s", "t", "si",
    "_ga", "_gl", "_hsenc", "_hsmi", "_ke",
    "trk", "trkInfo", "originalReferer",
    "algo", "algo_expid", "btsid", "ws_ab_test", "spm", "pvid", "scm",
}

# WebKit timestamp epoch (Jan 1, 1601) to Unix epoch offset
WEBKIT_EPOCH_OFFSET = 11644473600

# Mac Absolute Time epoch (Jan 1, 2001) to Unix epoch offset
MAC_ABSOLUTE_TIME_OFFSET = 978307200


def log_error(message: str) -> None:
    """Append error message to error log."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ERROR_LOG, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def webkit_to_datetime(webkit_timestamp: int) -> datetime:
    """Convert WebKit timestamp (microseconds since 1601) to datetime."""
    unix_timestamp = (webkit_timestamp / 1_000_000) - WEBKIT_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_timestamp)


def mac_absolute_to_datetime(mac_timestamp: float) -> datetime:
    """Convert Mac Absolute Time (seconds since 2001) to datetime."""
    unix_timestamp = mac_timestamp + MAC_ABSOLUTE_TIME_OFFSET
    return datetime.fromtimestamp(unix_timestamp)


def clean_url(url: str) -> str:
    """Remove tracking parameters from URL."""
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url

        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned_params = {
            k: v for k, v in params.items()
            if k.lower() not in TRACKING_PARAMS
        }

        cleaned_query = urlencode(cleaned_params, doseq=True)
        cleaned = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            cleaned_query,
            ""  # Remove fragment too
        ))
        return cleaned.rstrip("?")
    except Exception:
        return url


def escape_markdown(text: str) -> str:
    """Escape text for safe use in markdown links."""
    if not text:
        return "Untitled"
    # Remove newlines and excessive whitespace
    text = " ".join(text.split())
    # Escape brackets and pipes
    text = text.replace("[", "\\[").replace("]", "\\]")
    text = text.replace("|", "\\|")
    return text


def get_chrome_profiles() -> list[Path]:
    """Find all Chrome profile directories containing a History file."""
    if not CHROME_BASE.exists():
        return []

    profiles = []
    for item in CHROME_BASE.iterdir():
        if item.is_dir():
            history_file = item / "History"
            if history_file.exists():
                profiles.append(item)
    return profiles


def read_history_from_profile(profile_path: Path, since: datetime | None = None) -> list[dict]:
    """Read history entries from a Chrome profile."""
    history_file = profile_path / "History"
    if not history_file.exists():
        return []

    entries = []
    tmp_file = None

    try:
        # Copy database to avoid lock issues
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp_file.close()
        shutil.copy2(history_file, tmp_file.name)

        conn = sqlite3.connect(tmp_file.name)
        cursor = conn.cursor()

        # Build query
        query = """
            SELECT urls.url, urls.title, visits.visit_time
            FROM visits
            JOIN urls ON visits.url = urls.id
        """
        params = []

        if since:
            webkit_since = int((since.timestamp() + WEBKIT_EPOCH_OFFSET) * 1_000_000)
            query += " WHERE visits.visit_time >= ?"
            params.append(webkit_since)

        query += " ORDER BY visits.visit_time ASC"

        cursor.execute(query, params)

        for url, title, visit_time in cursor.fetchall():
            try:
                # Skip excluded URLs (chrome://, extensions, etc.)
                if url.startswith(EXCLUDED_PREFIXES):
                    continue

                dt = webkit_to_datetime(visit_time)
                entries.append({
                    "url": clean_url(url),
                    "title": escape_markdown(title or ""),
                    "timestamp": dt,
                    "profile": profile_path.name
                })
            except Exception as e:
                log_error(f"Failed to process entry: {e}")

        conn.close()

    except Exception as e:
        log_error(f"Failed to read history from {profile_path.name}: {e}")

    finally:
        if tmp_file and os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)

    return entries


def read_safari_history(since: datetime | None = None) -> list[dict]:
    """Read history entries from Safari."""
    if not SAFARI_HISTORY.exists():
        return []

    entries = []
    tmp_file = None

    try:
        # Copy database to avoid lock issues
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp_file.close()
        shutil.copy2(SAFARI_HISTORY, tmp_file.name)

        conn = sqlite3.connect(tmp_file.name)
        cursor = conn.cursor()

        # Build query - Safari uses different schema
        query = """
            SELECT history_items.url, history_items.title, history_visits.visit_time
            FROM history_visits
            JOIN history_items ON history_visits.history_item = history_items.id
        """
        params = []

        if since:
            mac_since = since.timestamp() - MAC_ABSOLUTE_TIME_OFFSET
            query += " WHERE history_visits.visit_time >= ?"
            params.append(mac_since)

        query += " ORDER BY history_visits.visit_time ASC"

        cursor.execute(query, params)

        for url, title, visit_time in cursor.fetchall():
            try:
                # Skip excluded URLs
                if url.startswith(EXCLUDED_PREFIXES):
                    continue

                dt = mac_absolute_to_datetime(visit_time)
                entries.append({
                    "url": clean_url(url),
                    "title": escape_markdown(title or ""),
                    "timestamp": dt,
                    "profile": "Safari"
                })
            except Exception as e:
                log_error(f"Failed to process Safari entry: {e}")

        conn.close()

    except Exception as e:
        log_error(f"Failed to read Safari history: {e}")

    finally:
        if tmp_file and os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)

    return entries


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url


def dedupe_entries(entries: list[dict]) -> list[dict]:
    """Remove duplicate URLs, keeping the first occurrence."""
    if not entries:
        return entries

    seen_urls = set()
    result = []
    for entry in entries:
        if entry["url"] not in seen_urls:
            seen_urls.add(entry["url"])
            result.append(entry)
    return result


def count_domains(entries: list[dict]) -> list[tuple[str, int]]:
    """Count visits per domain, sorted by count descending."""
    counts = {}
    for entry in entries:
        domain = get_domain(entry["url"])
        counts[domain] = counts.get(domain, 0) + 1
    return sorted(counts.items(), key=lambda x: (-x[1], x[0]))


def group_entries_by_day(entries: list[dict]) -> dict[date, list[dict]]:
    """Group entries by date."""
    days = {}
    for entry in entries:
        day_key = entry["timestamp"].date()
        if day_key not in days:
            days[day_key] = []
        days[day_key].append(entry)
    return days


def generate_day_markdown(day: date, entries: list[dict]) -> str:
    """Generate markdown content for a day's history."""
    day_name = day.strftime("%A, %B %d, %Y")
    lines = [f"# Browser History: {day_name}", ""]

    # Sort by timestamp and dedupe (keeps first visit to each URL)
    sorted_entries = sorted(entries, key=lambda e: e["timestamp"])
    deduped_entries = dedupe_entries(sorted_entries)

    # Add domain summary
    domain_counts = count_domains(deduped_entries)
    if domain_counts:
        domain_strs = [f"{domain} ({count})" for domain, count in domain_counts[:10]]
        if len(domain_counts) > 10:
            domain_strs.append(f"... and {len(domain_counts) - 10} more")
        lines.append(f"**Domains:** {', '.join(domain_strs)}")
        lines.append("")

    # Add visit entries
    lines.append("## Visits")
    lines.append("")
    for entry in deduped_entries:
        time_str = entry["timestamp"].strftime("%H:%M")
        title = entry["title"] or "Untitled"
        url = entry["url"]
        lines.append(f"- {time_str} - [{title}]({url})")

    lines.append("")
    return "\n".join(lines)


def write_day_file(day: date, entries: list[dict]) -> None:
    """Write a daily digest markdown file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = OUTPUT_DIR / f"{day.isoformat()}.md"
    content = generate_day_markdown(day, entries)

    with open(filename, "w") as f:
        f.write(content)


def get_state_file() -> Path:
    """Get path to state file tracking last run."""
    return OUTPUT_DIR / ".last_run"


def get_last_run() -> datetime | None:
    """Get timestamp of last successful run."""
    state_file = get_state_file()
    if not state_file.exists():
        return None
    try:
        timestamp = float(state_file.read_text().strip())
        return datetime.fromtimestamp(timestamp)
    except Exception:
        return None


def set_last_run(dt: datetime) -> None:
    """Record timestamp of this run."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state_file = get_state_file()
    state_file.write_text(str(dt.timestamp()))


def main() -> None:
    """Main entry point."""
    # Determine start date
    last_run = get_last_run()
    today = datetime.now().date()
    if last_run:
        # Get entries since last run, but regenerate full current day
        day_start = datetime.combine(today, datetime.min.time())
        since = min(last_run - timedelta(hours=1), day_start)
    else:
        # First run: backfill all available history
        since = None

    all_entries = []

    # Collect from Chrome profiles
    chrome_profiles = get_chrome_profiles()
    for profile in chrome_profiles:
        entries = read_history_from_profile(profile, since)
        all_entries.extend(entries)

    # Collect from Safari
    safari_entries = read_safari_history(since)
    all_entries.extend(safari_entries)

    if not all_entries:
        if not chrome_profiles and not SAFARI_HISTORY.exists():
            log_error("No Chrome profiles or Safari history found")
        set_last_run(datetime.now())
        return

    # Group by day and write files
    days = group_entries_by_day(all_entries)

    for date, entries in days.items():
        # For historical days, only write if file doesn't exist
        # For current day, always regenerate
        is_today = (date == today)
        filename = OUTPUT_DIR / f"{date.isoformat()}.md"

        if is_today or not filename.exists():
            write_day_file(date, entries)

    set_last_run(datetime.now())


if __name__ == "__main__":
    main()
