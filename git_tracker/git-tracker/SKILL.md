---
name: git-tracker
description: Fetch developer commit statistics from remote git repositories via SSH or HTTPS. Runs a Python script that outputs JSON with author name, lines added/removed, time spent per commit, and branch info. Use this skill whenever the user or a cron job asks for git activity reports, developer contribution summaries, code review stats, or daily standups based on git data. Supports approximate time estimation (caps overnight/weekend gaps at 8h). Always use --approximate flag for human-readable reports. Triggered by cron daily at 08:00 CET.
compatibility: Requires Python 3.9+, git CLI, and SSH access for SSH repositories
metadata:
  author: nkte-X
  version: "1.1"
---

# Git Tracker Skill

Fetch and track developer activity from remote git repositories via SSH or HTTPS.

## Quick Start

```bash
python3 ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/scripts/git_tracker.py --all --approximate
python3 ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/scripts/git_tracker.py --repo <name> --approximate
python3 ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/scripts/git_tracker.py --show-config
```

## Directory Structure

```
OPENCLAW_WORKSPACE_DIR/                 # ~/.openclaw/workspace/ by default
├── skills/
│   └── git-tracker/                    # Skill directory (replaceable on update)
│       ├── SKILL.md                    # This skill file
│       ├── scripts/
│       │   └── git_tracker.py          # Main script
│       └── references/
│           └── UPDATE.md               # Update procedure
└── git_tracker/                        # Persistent data (PRESERVED on update)
    ├── config.json                     # Repository configuration
    ├── config-example.json             # Example config template
    └── data/                           # Daily statistics files
        └── stats_{dd_mm_yyyy}.json
```

**Important:**
- `OPENCLAW_WORKSPACE_DIR`: OpenClaw workspace (`~/.openclaw/workspace/` by default)
- `skills/git-tracker/` is replaceable on update — safe to overwrite
- `git_tracker/` (config + data) is persistent — never overwrite during updates

## Configuration

Config file: `${OPENCLAW_WORKSPACE_DIR}/git_tracker/config.json`

```json
{
  "repositories": [
    {
      "name": "my-repo",
      "ssh_url": "git@github.com:org/repo.git",
      "branch_name": "main",
      "user_email": "dev@company.com"
    }
  ],
  "settings": {
    "num_days": 10
  },
  "ssh_dir": "~/.ssh"
}
```

**Repository fields:**
- `name` (required): Repository identifier
- `ssh_url` (optional): SSH URL (git@host:path)
- `https_url` (optional): HTTPS URL with optional token auth
- `branch_name` (optional): Branch to fetch (default: auto-discover recent branches)
- `user_email` (optional): Filter commits by author email

**URL validation:** When user provides a URL, validate if it's SSH or HTTPS and save to the correct field.

**SSH Key Resolution Priority:**
1. Environment variable: `SSH_KEY_DIR`
2. Config: `config.ssh_dir`
3. Default: `~/.ssh`

## CLI Options

Execute from the skill's scripts directory:

```bash
python3 ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/scripts/git_tracker.py --all --approximate
python3 ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/scripts/git_tracker.py --repo <name>
python3 ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/scripts/git_tracker.py --show-config
```

| Flag | Description |
|------|-------------|
| `--all` | Process all repositories from config |
| `--repo <name>` | Process specific repository |
| `--num-days <n>` | Number of days to look back (default: from config.json) |
| `--init` | Create default config |
| `--show-config` | Display current configuration |
| `--approximate` | Cap spent_time at 8h workday, flag approximate entries |

## Output Data Schema

Script returns JSON structure:

```json
{
  "repo_name": [
    {
      "git_name": "John Doe",
      "username": "johnd",
      "email": "john@company.com",
      "rows_added": 150,
      "rows_removed": 20,
      "spent_time": "0d2h30m",
      "timestamp": "2025-03-06T10:30:00+01:00",
      "branch": "main",
      "error": "-",
      "approximate": false
    }
  ]
}
```

**Fields:**
- `git_name`: Author name from commit
- `username`: Email prefix (before @) or author name if no email
- `email`: Author email
- `rows_added`: Lines added (sum of all files in commit)
- `rows_removed`: Lines removed (sum of all files in commit)
- `spent_time`: Time since previous commit (format: XdXhXm)
- `timestamp`: Commit timestamp (ISO format)
- `branch`: Branch name
- `error`: Error message or "-" for success
- `approximate`: Boolean — `true` when `spent_time` was capped at 8h (raw delta exceeded a workday), `false` when `spent_time` is the actual inter-commit delta

## Approximate Time Heuristics

When `approximate` is `true`, `spent_time` shows `0d8h0m` (the cap) — the real gap was longer but included non-working time. Estimate actual work time from `rows_added + rows_removed`:

| Lines changed (added+removed) | Estimated work time | Example |
|-------------------------------|--------------------:|---------|
| 1-10                          | ~15-30min           | 5 lines → "~20min" |
| 11-30                         | ~30min-1h           | 20 lines → "~45min" |
| 31-100                        | ~1-4h               | 60 lines → "~2h" |
| 100+                          | ~4-8h               | 200 lines → "~6h" |

Rules:
- When `approximate` is `true`: use the table above, prefix with "~"
- When `approximate` is `false`: use exact `spent_time` value as-is
- When `spent_time` is empty: this is the first commit in the window, show "-" or omit

## Output Formatting Rules

When presenting git tracker data to the user, follow these rules exactly:

1. **Run the script** with `--approximate` flag (always, unless user explicitly asks for raw data)
2. **Read the JSON output** from the daily stats file or stdout
3. **Format each entry** using the template in "User Output Format" below
4. **Sort order**: entries are already sorted newest-first by the script
5. **Group by date**: group entries by calendar date, show date as header
6. **Approximate handling**:
   - If `approximate: false` → show `spent_time` exactly as-is (e.g., "0d2h30m" → "2h 30m")
   - If `approximate: true` → calculate from lines changed using the heuristics table above, prefix with "~"
   - If `spent_time` is empty → show "-"
7. **Human-readable spent_time**: strip leading zeros and "d" when days=0 (e.g., "0d2h30m" → "2h 30m", "1d3h0m" → "1d 3h")

**Example transformations:**

Input: `{"rows_added": 36, "rows_removed": 12, "spent_time": "0d8h0m", "approximate": true}`
Output: spent_time shown as "~2-3h" (48 lines changed → medium range)

Input: `{"rows_added": 3, "rows_removed": 2, "spent_time": "0d0h10m", "approximate": false}`
Output: spent_time shown as "10m" (exact, not approximate)

## User Output Format Setup

If the "User Output Format" section below still shows `[USER_PREFERENCES_HERE]`, ask the user these questions on first interaction:

1. **Output format**: Markdown table / JSON / CSV / Custom
2. **Date format**: DD.MM.YYYY / DD-MM-YY / YYYY-MM-DD / Custom
3. **Author display**: Username (email prefix) / Full name / Email / Custom

Then update the section below with their choices and a concrete template.

## User Output Format

[USER_PREFERENCES_HERE]

<!--
Example (replace placeholder above with user's actual preferences):

**Output Format:** Markdown table
**Date Format:** DD.MM.YYYY
**Author Format:** Username (email prefix)

**Template:**
| date | repo | +lines | -lines | author | branch | time |
|------|------|--------|--------|--------|--------|------|
| {DD.MM.YYYY} | {repo_name} | +{rows_added} | -{rows_removed} | {username} | {branch} | {spent_time_formatted} |
-->

## Error Handling

- Connection failures return entry with error message
- Invalid URLs return "hostname contains invalid characters"
- Authentication failures return specific error
- Empty results if no commits match filter

## URL Formats

**SSH:**
- `git@github.com:org/repo.git`
- `ssh://git@gitlab.com/group/project`

**HTTPS:**
- `https://github.com/org/repo.git`
- `https://token@bitbucket.org/team/repo.git`

## Notes

- Clones repositories temporarily to fetch logs
- Automatically cleans up temp directories
- Outputs daily stats to `${OPENCLAW_WORKSPACE_DIR}/git_tracker/data/stats_{dd_mm_yyyy}.json` with creation date in filename
- All entries from all repos are merged into single daily file
- Agent must format script output according to user preferences in "User Output Format" section

## Updating

See [references/UPDATE.md](references/UPDATE.md) for the full update procedure.
