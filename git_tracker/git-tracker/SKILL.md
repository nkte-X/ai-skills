---
name: git-tracker
description: Track developer activity from remote git repositories via SSH or HTTPS. Use to fetch git statistics including git name, username, rows added, rows removed, and time between commits (spent time). Supports both SSH and HTTPS URLs, configurable SSH key directory, email filtering. Writes daily statistics to ROOT_DIR/git_tracker/data/ with date-based filenames. Returns formatted output based on user preferences set during setup. Integrates with OpenClaw for formatting and pushing to communication channels. Use when agent needs to track git activity, generate reports, or analyze developer contributions.
---

# Git Tracker Skill

Fetch and track developer activity from remote git repositories via SSH or HTTPS.

## Quick Start

```bash
python3 script/git_tracker.py --all
python3 script/git_tracker.py --repo <name>
python3 script/git_tracker.py --show-config
python3 script/git_tracker.py --init
```

## Directory Structure

```
ROOT_DIR/                           # Main OpenClaw agent root (ROOT_EXEC dir)
├── scripts/
│   └── git_tracker.py              # Main script (execute from ROOT_DIR)
├── git_tracker/
│   ├── config.json                 # Repository configuration (PRESERVED on update)
│   └── data/                       # Daily statistics files (PRESERVED on update)
│       └── stats_{dd_mm_yyyy}.json # Stats file with creation date
OPENCLAW_WORKSPACE_DIR/
└── skills/
    └── git-tracker/
        └── SKILL.md                # This skill file
```

**Important directories:**
- `ROOT_DIR`: Main OpenClaw agent root directory (execution directory)
- `OPENCLAW_WORKSPACE_DIR`: OpenClaw workspace for skills (`~/.openclaw/workspace/` by default)
- Config and data directories in `ROOT_DIR/git_tracker/` are preserved during updates

## Configuration

Config file: `ROOT_DIR/git_tracker/config.json`

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

Execute script from `ROOT_DIR/scripts/`:

```bash
cd ROOT_DIR
python3 scripts/git_tracker.py --all
python3 scripts/git_tracker.py --repo <name>
python3 scripts/git_tracker.py --show-config
python3 scripts/git_tracker.py --init
```

| Flag | Description |
|------|-------------|
| `--all` | Process all repositories from config |
| `--repo <name>` | Process specific repository |
| `--num-days <n>` | Number of days to look back (default: 10) |
| `--init` | Create default config |
| `--show-config` | Display current configuration |

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
      "error": "-"
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

## User Output Format Settings

When setting up the skill, agent must ask user for output format preferences:

**Question 1: Output Data Format**
```
What format would you like to use for displaying git tracker statistics?

Options:
1. Markdown table
2. JSON format
3. CSV format
4. Custom format (specify)

Examples:
Markdown:
| date | repo_name | rows_added | rows_removed | username | branch | spent_time |
|------|-----------|------------|--------------|----------|--------|------------|
| 06.03.2026 | backend | +70 | -20 | Alex | main | 0d2h30m |

JSON:
[{"date": "06.03.2026", "repo_name": "backend", "rows_added": 70, "rows_removed": 20, "username": "Alex", "branch": "main", "spent_time": "2h30m"}]
```

**Question 2: Date Format**
```
What date format do you prefer?

Options:
1. DD-MM-YYYY
2. DD-MM-YY
3. YYYY-MM-DD
4. Custom (specify)
```

**Question 3: Author Name Format**
```
How should the author be displayed?

Options:
1. Username (email prefix)
2. Full name
3. Email address
4. Custom format (specify)
```

**After user selects preferences:**
1. Add "User Output Format" section to this SKILL.md with the selected format
2. Agent MUST always format output according to these settings
3. Apply date format to `timestamp` field
4. Apply author format to `username` field
5. Format `spent_time` as approximate time spent for commit

## User Output Format

[USER_PREFERENCES_HERE]

<!-- 
Example format for user preferences (update this section during setup):

**Output Format:** Markdown table

**Date Format:** DD-MM-YYYY

**Author Format:** Username (email prefix)

**Table Template:**
| date | repo_name | rows_added | rows_removed | username | branch | spent_time |
|------|-----------|------------|--------------|----------|--------|------------|
| {date} | {repo_name} | +{rows_added} | -{rows_removed} | {username} | {branch} | {spent_time} |

**Field Mappings:**
- date: timestamp formatted as DD-MM-YYYY
- repo_name: repository name from config
- rows_added: rows_added (with + prefix)
- rows_removed: rows_removed (with - prefix)
- username: email prefix (before @)
- branch: branch name
- spent_time: approximate time spent based on spent_time field
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
- Outputs daily stats to `ROOT_DIR/git_tracker/data/stats_{dd_mm_yyyy}.json` with creation date in filename
- All entries from all repos are merged into single daily file
- Agent must format script output according to user preferences in "User Output Format" section

## Skill Update Procedure

When updating to a new version of the skill:

1. **Update Python script:**
   ```bash
   cp git_tracker/script/git_tracker.py ROOT_DIR/scripts/
   ```

2. **Update skill file:**
   ```bash
   cp git_tracker/git-tracker/SKILL.md OPENCLAW_WORKSPACE_DIR/skills/git-tracker/
   ```

3. **PRESERVE user settings:**
   - Keep `ROOT_DIR/git_tracker/config.json` unchanged
   - Keep `ROOT_DIR/git_tracker/data/` directory unchanged
   - When updating SKILL.md, preserve the "User Output Format" section

4. **Restart OpenClaw** to load updated skill

**Important:** Never overwrite `config.json` or `data/` directory during updates as they contain user-specific configurations and accumulated statistics.
