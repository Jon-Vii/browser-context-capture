# Browser Context Capture

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-blue.svg)](https://www.apple.com/macos/)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)
[![Chrome](https://img.shields.io/badge/Browser-Chrome-red.svg)](https://www.google.com/chrome/)
[![Safari](https://img.shields.io/badge/Browser-Safari-blue.svg)](https://www.apple.com/safari/)

Automatically capture your Chrome and Safari browsing history into daily markdown digests. Perfect for personal recall, journaling, and feeding context to AI agents.

## What This Does

- 📅 **Daily markdown files** of all your browsing activity
- 🌐 **Chrome + Safari support** including iOS history via iCloud sync
- 🤖 **AI-friendly format** for easy integration with agents and LLMs
- ⚡ **Lightweight** - No extensions, no background processes (just hourly snapshots)
- 📍 **macOS native** - Uses launchd for scheduling, reads your existing browser databases

## Quick Start

```bash
./install.sh
```

That's it. The script will:
1. Create `~/memex/browser/` for your daily history files
2. Set up hourly automatic captures via launchd
3. Backfill historical data from your browsers

Files appear as `~/memex/browser/2025-12-30.md`, `2025-12-31.md`, etc.

## Example Output

```markdown
# Browser History: Tuesday, December 30, 2025

**Domains:** github.com (12), claude.ai (8), stackoverflow.com (5), ...

## Visits

- 09:15 - [Claude Code - GitHub](https://github.com/anthropics/claude-code)
- 09:32 - [Rust Async Book](https://rust-lang.github.io/async-book/)
- 10:01 - [How to handle async errors - Stack Overflow](https://stackoverflow.com/questions/12345)
```

## AI Agent Integration

The markdown format makes your browsing history trivially accessible to AI agents and LLMs, enabling powerful contextual assistance:

### Use Cases

**Research Continuity**
- "What articles did I read about Rust async yesterday?"
- "Find that GitHub repo I was looking at this morning"
- AI agents can reference your actual browsing to provide specific answers

**Context-Aware Assistance**
- Agents see what you've been researching and can offer relevant suggestions
- "Based on your recent Swift documentation reading, here's how to..."
- No need to explain what you've been working on - your browser history provides the context

**Personal Knowledge Base**
- Daily files integrate seamlessly with note-taking systems (Obsidian, Logseq, etc.)
- AI can cross-reference browser history with your notes and documents
- Build a searchable timeline of your digital research

### Implementation

Simply point your AI agent to `~/memex/browser/` and it can:
1. Read today's file for recent context
2. Search across date ranges for specific topics
3. Correlate browsing patterns with your questions
4. Reference specific URLs and timestamps in responses

The markdown format means no special parsing - any LLM can instantly understand and utilize your browsing history.

## Features

- **Multi-profile Chrome support** - Captures history from all your Chrome profiles
- **iOS integration** - Safari history includes iCloud-synced activity from your iPhone/iPad
- **Clean URLs** - Tracking parameters (utm_*, fbclid, gclid, etc.) stripped automatically
- **Consecutive dedup** - Multiple visits to the same page in quick succession shown as one
- **Error logging** - Problems logged to `~/.memex/browser/.errors.log`, doesn't crash if one browser is missing
- **Python 3.9+** - Works on any recent macOS without external dependencies

## System Requirements

- macOS 10.13 or later
- Python 3.9+ (pre-installed on macOS)
- Chrome or Safari (or both)

## Permissions

### Safari Access (Full Disk Access)

Safari's history database is protected by macOS. To capture Safari history, you need to grant **Full Disk Access** to Python:

1. Open **System Settings** → **Privacy & Security** → **Full Disk Access**
2. Click the lock and authenticate
3. Click **+** and add `/usr/bin/python3`
4. Ensure the checkbox is enabled

Without this permission, Chrome history will still be captured, but Safari will be skipped.

### Troubleshooting Permissions

Check the status file to see if there are any issues:

```bash
cat ~/memex/browser/.status
```

Example output when everything works:
```json
{
  "sources": {
    "Chrome/Default": {"status": "ok", "entries": 25},
    "Safari": {"status": "ok", "entries": 64}
  },
  "has_errors": false,
  "last_run": "2025-12-31T01:20:35"
}
```

If Safari shows a permission error, a `PERMISSION_ERROR.txt` file will appear in `~/memex/browser/` with instructions. This file is automatically removed once the issue is resolved.

## Recent Updates

### Better Error Visibility
- Added `.status` JSON file showing health of each browser source
- macOS notification on first permission error (doesn't spam on repeat runs)
- Visible `PERMISSION_ERROR.txt` file when access is blocked, with fix instructions
- Fixed Safari schema compatibility (title column location)

### Migrate to Daily Files
Files are now organized by date (`YYYY-MM-DD.md`) for easier browsing and integration with note systems.

### Safari Support
Full support for Safari history including iOS devices via iCloud sync.

### Python 3.9 Compatibility
Fixed compatibility issues to work on older macOS versions that ship with Python 3.9.

## Technical Details

See [SPEC.md](SPEC.md) for:
- Detailed architecture and data flow
- Chrome and Safari database schema
- URL cleaning and markdown escaping rules
- Error handling and concurrency details
- Complete launchd configuration

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.memex.browser-capture.plist
rm ~/Library/LaunchAgents/com.memex.browser-capture.plist
```

Optionally remove captured history:
```bash
rm -rf ~/memex/browser/
```

## How It Works

1. **Runs hourly** via launchd while you're logged in
2. **Reads** Chrome and Safari history databases directly (no browser extensions)
3. **Generates** a daily markdown file for each date
4. **Updates** today's file on each run with new visits
5. **Backfills** historical data on first installation (Chrome typically retains ~90 days)

No network requests, no cloud sync, no content extraction - just timestamps, URLs, and page titles from your existing browser databases.

---

**macOS only.** Uses native launchd scheduling and reads macOS browser database paths.
