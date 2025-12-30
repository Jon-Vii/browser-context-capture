# Browser Context Capture

A lightweight tool that captures Chrome and Safari browsing history into daily markdown digests for personal recall and AI agent consumption.

## Overview

Reads Chrome and Safari history databases and generates human-readable, AI-friendly daily digest files. Runs automatically in the background via macOS launchd. Safari history synced via iCloud includes browsing from iOS devices.

## Goals

- **Minimal**: No browser extension, no complex infrastructure
- **Useful**: Capture what matters - where you've been, when
- **AI-ready**: Markdown format trivially consumable by any LLM or agent
- **Unobtrusive**: Silent background operation, negligible resource usage

## Architecture

```
Chrome History DB ──┐
(SQLite)            ├──▶ Python Script ──▶ Daily Markdown Files
Safari History DB ──┘    (hourly via launchd)    (~/memex/browser/)
(SQLite)
```

### Data Sources

**Chrome** stores browsing history in SQLite databases per profile:

```
~/Library/Application Support/Google/Chrome/*/History
```

This captures Default, Profile 1, Profile 2, etc.

**Safari** stores browsing history in a single SQLite database:

```
~/Library/Safari/History.db
```

With iCloud sync enabled, this includes history from iOS devices.

### Output Location

```
~/memex/browser/
├── 2025-12-30.md
├── 2025-12-31.md
├── .errors.log
└── ...
```

### File Format

Daily files use ISO 8601 date format (YYYY-MM-DD).

```markdown
# Browser History: Monday, December 30, 2025

**Domains:** github.com (12), claude.ai (8), stackoverflow.com (5), ...

## Visits

- 09:15 - [Claude Code - GitHub](https://github.com/anthropics/claude-code)
- 09:32 - [Rust Async Book](https://rust-lang.github.io/async-book/)
- 10:01 - [How to handle async errors - Stack Overflow](https://stackoverflow.com/questions/12345)
- 11:00 - [Apple Developer Documentation](https://developer.apple.com/documentation/)
...
```

## Implementation Details

### Technology Stack

- **Language**: Python 3 (pre-installed on macOS)
- **Scheduler**: launchd (native macOS daemon system)
- **Database**: SQLite3 (reading Chrome's existing DB)

### Script Behavior

1. Runs hourly via launchd
2. Discovers all Chrome profiles
3. Reads history for the current day (and past days on first run)
4. Regenerates daily markdown files
5. Creates `~/memex/browser/` directory if it doesn't exist

### Historical Backfill

On first run, the script generates digests for all available history (Chrome typically retains ~90 days). Subsequent runs only update the current day's file.

### URL Cleaning

Tracking parameters are stripped for cleaner, more readable URLs:

- `utm_*` (all UTM parameters)
- `fbclid`
- `gclid`
- `ref`
- `source`
- `mc_eid`
- Other common tracking params

Example:
```
Before: https://example.com/article?id=123&utm_source=twitter&fbclid=abc
After:  https://example.com/article?id=123
```

### Markdown Escaping

Page titles are escaped to prevent breaking markdown formatting:
- Brackets `[]` escaped
- Pipes `|` escaped
- Newlines stripped

### Chrome History Schema

Relevant tables/columns:
- `urls`: `id`, `url`, `title`
- `visits`: `url` (foreign key), `visit_time` (WebKit timestamp)

WebKit timestamp = microseconds since Jan 1, 1601. Conversion:
```python
unix_timestamp = (webkit_timestamp / 1_000_000) - 11644473600
```

### Concurrency Consideration

Chrome locks its history database while running. The script:
1. Copies the database to a temp location
2. Reads from the copy
3. Cleans up after

This avoids "database is locked" errors.

### Error Handling

Errors are logged to `~/memex/browser/.errors.log`:
- Chrome not installed / history DB not found
- Database read failures
- File write failures

The script continues operation when possible (e.g., if one profile fails, others still process).

## Scheduling

### launchd Configuration

Plist location: `~/Library/LaunchAgents/com.memex.browser-capture.plist`

Runs hourly while user is logged in.

## Data Captured Per Visit

| Field | Source | Example |
|-------|--------|---------|
| Timestamp | `visits.visit_time` | `09:15` |
| Title | `urls.title` | `Claude Code - GitHub` |
| URL | `urls.url` (cleaned) | `https://github.com/anthropics/claude-code` |

No content extraction, no network requests, no page fetching.

## What This Does NOT Do

- **No browser extension**: Reads existing browser databases
- **No content extraction**: Just URL, title, timestamp
- **No cloud sync**: Local databases only (but Safari's local DB includes iCloud-synced history)
- **Limited browser support**: Chrome and Safari only (no Firefox, Edge, etc.)

## Filtering & Deduplication

- **Excluded URLs**: `chrome://`, `chrome-extension://`, `edge://`, `about:`, `file://`, `devtools://` are filtered out
- **Consecutive deduplication**: Repeated visits to the same URL in sequence are collapsed to the first occurrence
- **Domain summary**: Top 10 domains with visit counts shown at the top of each file for quick scanning

## Directory Structure

```
browser-context-capture/
├── SPEC.md
├── src/
│   └── capture.py          # Main script
├── install.sh              # Installation script
└── com.memex.browser-capture.plist  # launchd config
```

## Installation

```bash
./install.sh
```

This will:
1. Create `~/memex/browser/` directory
2. Copy launchd plist to `~/Library/LaunchAgents/`
3. Load the launchd job
4. Run initial backfill of historical data

## Uninstallation

```bash
launchctl unload ~/Library/LaunchAgents/com.memex.browser-capture.plist
rm ~/Library/LaunchAgents/com.memex.browser-capture.plist
```

Optionally remove data:
```bash
rm -rf ~/memex/browser/
```

## Platform

macOS only (uses launchd, Chrome's macOS database path).
