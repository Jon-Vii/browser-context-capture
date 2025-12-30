#!/usr/bin/env python3
"""
Browser Context Capture

Reads Chrome browser history and generates weekly markdown digests.
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Configuration
OUTPUT_DIR = Path.home() / "memex" / "browser"
CHROME_BASE = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
ERROR_LOG = OUTPUT_DIR / ".errors.log"

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


def get_iso_week_range(year: int, week: int) -> tuple[datetime, datetime]:
    """Get the start (Monday) and end (Sunday) dates for an ISO week."""
    jan4 = datetime(year, 1, 4)
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())
    week_start = start_of_week1 + timedelta(weeks=week - 1)
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return week_start, week_end


def format_week_header(year: int, week: int) -> str:
    """Format the header for a weekly digest file."""
    week_start, week_end = get_iso_week_range(year, week)
    start_str = week_start.strftime("%b %d")
    end_str = week_end.strftime("%b %d")
    return f"# Browser History: {year}-W{week:02d} ({start_str} - {end_str})"


def group_entries_by_week(entries: list[dict]) -> dict[tuple[int, int], list[dict]]:
    """Group entries by ISO year and week number."""
    weeks = {}
    for entry in entries:
        iso_cal = entry["timestamp"].isocalendar()
        key = (iso_cal.year, iso_cal.week)
        if key not in weeks:
            weeks[key] = []
        weeks[key].append(entry)
    return weeks


def generate_week_markdown(year: int, week: int, entries: list[dict]) -> str:
    """Generate markdown content for a week's history."""
    lines = [format_week_header(year, week), ""]

    # Group by day
    days = {}
    for entry in entries:
        day_key = entry["timestamp"].date()
        if day_key not in days:
            days[day_key] = []
        days[day_key].append(entry)

    for day in sorted(days.keys()):
        day_entries = days[day]
        day_name = day.strftime("%A, %b %d")
        lines.append(f"## {day_name}")
        lines.append("")

        for entry in sorted(day_entries, key=lambda e: e["timestamp"]):
            time_str = entry["timestamp"].strftime("%H:%M")
            title = entry["title"] or "Untitled"
            url = entry["url"]
            lines.append(f"- {time_str} - [{title}]({url})")

        lines.append("")

    return "\n".join(lines)


def write_week_file(year: int, week: int, entries: list[dict]) -> None:
    """Write a weekly digest markdown file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = OUTPUT_DIR / f"{year}-W{week:02d}.md"
    content = generate_week_markdown(year, week, entries)

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
    profiles = get_chrome_profiles()

    if not profiles:
        log_error("No Chrome profiles found")
        return

    # Determine start date
    last_run = get_last_run()
    if last_run:
        # Get entries since last run, but regenerate full current week
        iso_cal = datetime.now().isocalendar()
        week_start, _ = get_iso_week_range(iso_cal.year, iso_cal.week)
        since = min(last_run - timedelta(hours=1), week_start)
    else:
        # First run: backfill all available history
        since = None

    # Collect entries from all profiles
    all_entries = []
    for profile in profiles:
        entries = read_history_from_profile(profile, since)
        all_entries.extend(entries)

    if not all_entries:
        set_last_run(datetime.now())
        return

    # Group by week and write files
    weeks = group_entries_by_week(all_entries)

    for (year, week), entries in weeks.items():
        # For historical weeks, only write if file doesn't exist
        # For current week, always regenerate
        iso_cal = datetime.now().isocalendar()
        is_current_week = (year == iso_cal.year and week == iso_cal.week)

        filename = OUTPUT_DIR / f"{year}-W{week:02d}.md"

        if is_current_week or not filename.exists():
            if filename.exists() and is_current_week:
                # For current week, merge with existing entries
                # (in case of multiple runs, we don't want to lose data)
                pass  # Currently regenerating full week from Chrome

            write_week_file(year, week, entries)

    set_last_run(datetime.now())


if __name__ == "__main__":
    main()
