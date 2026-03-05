---
name: git-tracker
description: Track developer activity from remote git repositories via SSH or HTTPS. Use to fetch git statistics including git name, username, rows added, rows removed, and time between commits (spent time). Supports both SSH and HTTPS URLs, configurable SSH key directory, email filtering. Writes daily statistics to local JSON file and returns last n rows. Integrates with OpenClaw for formatting and pushing to communication channels.
---

# Git Tracker Skill

Fetch and track developer activity from remote git repositories.

## Quick Start

```bash
python3 script/git_tracker.py --all
python3 script/git_tracker.py --repo <name>
python3 script/git_tracker.py --show-config
python3 script/git_tracker.py --init
```

## Configuration

Config file: `git_tracker/config.json`

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
    "num_commit": 10
  },
  "ssh_dir": "~/.ssh"
}
```

**Repository fields:**
- `name` (required): Repository identifier
- `ssh_url` (optional): SSH URL (git@host:path)
- `https_url` (optional): HTTPS URL with optional token auth
- `branch_name` (optional): Branch to fetch (default: default branch)
- `user_email` (optional): Filter commits by author email

**SSH Key Resolution Priority:**
1. Environment variable: `SSH_KEY_DIR`
2. Config: `config.ssh_dir`
3. Default: `~/.ssh`

## CLI Options

| Flag | Description |
|------|-------------|
| `--all` | Process all repositories from config |
| `--repo <name>` | Process specific repository |
| `--num-commits <n>` | Number of commits (default: 10) |
| `--init` | Create default config |
| `--show-config` | Display current configuration |

## Output Data Schema

```json
[
  {
    "git_name": "John Doe",
    "username": "johnd",
    "email": "john@company.com",
    "rows_added": 150,
    "rows_removed": 20,
    "spent_time": "2h30m",
    "timestamp": "2025-03-06T10:30:00+01:00",
    "error": "-"
  }
]
```

**Fields:**
- `git_name`: Author name from commit
- `username`: Email prefix (before @)
- `email`: Author email
- `rows_added`: Lines added (sum of all files in commit)
- `rows_removed`: Lines removed (sum of all files in commit)
- `spent_time`: Time since previous commit (format: Xs, Xm, Xh, Xd)
- `timestamp`: Commit timestamp (ISO format)
- `error`: Error message or "-" for success

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
- Outputs daily stats to `git_tracker/data/stats_{dd_mm_yyyy}.json`
- All entries from all repos are merged into single daily file
