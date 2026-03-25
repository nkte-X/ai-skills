# Git Tracker Skill -- Setup Manual

This document describes how to install or update the **git-tracker** skill on an OpenClaw instance.

## Prerequisites

- Python 3.9+, git CLI installed on the server

**Source repository:** `https://github.com/nkte-X/ai-skills.git` (branch: master)

---

## Detect Install vs Update

Check if `skills/git-tracker/` exists in the workspace. If yes, follow Update Procedure. If no, follow Full Installation.

---

## Update Procedure

Use this when the skill is already installed and you want to pull the latest version.

### 1. Clone latest source

```bash
cd /tmp && git clone https://github.com/nkte-X/ai-skills.git git_tracker_update
```

### 2. Backup User Output Format

Copy the text between `## User Output Format` and the next `##` heading from the current `skills/git-tracker/SKILL.md` -- this contains user-specific preferences that must be preserved.

### 3. Update skill directory

```bash
cp -r /tmp/git_tracker_update/git_tracker/git-tracker/* skills/git-tracker/
```

### 4. Restore User Output Format

Paste the backed-up preferences into the new SKILL.md, replacing `[USER_PREFERENCES_HERE]`.

### 5. Config and data are safe

Config and data live at `~/git-tracker/` (outside the skill directory) and are not affected by updates.

### 6. Cleanup and restart

```bash
rm -rf /tmp/git_tracker_update
openclaw restart
```

### 7. Verify

```bash
python3 skills/git-tracker/scripts/git_tracker.py --show-config
python3 skills/git-tracker/scripts/git_tracker.py --all --approximate
```

---

## Full Installation

### Step 1: Clone Repository

```bash
cd /tmp && git clone https://github.com/nkte-X/ai-skills.git git_tracker_install
```

### Step 2: Copy Skill Directory

```bash
mkdir -p skills/git-tracker
cp -r /tmp/git_tracker_install/git_tracker/git-tracker/* skills/git-tracker/
```

This copies SKILL.md, scripts/, references/, and assets/ into the skills workspace.

### Step 3: Initialize Config

```bash
python3 skills/git-tracker/scripts/git_tracker.py --init
```

This creates:
- `~/git-tracker/config.json` -- default config (edit with your repos)
- `~/git-tracker/data/` -- daily statistics storage
- `~/git-tracker/backups/` -- auto-backup directory

Alternatively, copy the template manually:
```bash
mkdir -p ~/git-tracker
cp skills/git-tracker/assets/config.template.json ~/git-tracker/config.json
```

### Step 4: Configure Tracked Repositories

Ask the user for each repository they want to track:
- **Repository URL** -- SSH (`git@github.com:org/repo.git`) or HTTPS (`https://github.com/org/repo.git`)
- **Display name** -- a short identifier (e.g., "backend", "api")
- **Branch** -- specific branch to track, or blank for auto-discover

Validate each URL: if starts with `git@` or `ssh://` → write to `ssh_url`, if starts with `https://` → write to `https_url`.

Ask the user:
- **How many days back to track?** (write to `settings.num_days`, default 10)
- **SSH key directory?** (write to `ssh_dir`, default `~/.ssh`)

Write the completed config to `~/git-tracker/config.json`.

Example config:
```json
{
  "_schema_version": 1,
  "repositories": [
    {
      "name": "backend",
      "ssh_url": "git@github.com:org/backend.git",
      "branch_name": "main"
    }
  ],
  "settings": {
    "num_days": 8
  },
  "ssh_dir": "~/.ssh"
}
```

### Step 5: Set Up User Output Format

Read `skills/git-tracker/SKILL.md`. If the "User Output Format" section shows `[USER_PREFERENCES_HERE]`, ask the user:

1. **Output format** -- Markdown table / JSON / CSV / Custom
2. **Date format** -- DD.MM.YYYY / DD-MM-YY / YYYY-MM-DD / Custom
3. **Author display** -- Username (email prefix) / Full name / Email / Custom

Write their choices into the "User Output Format" section of SKILL.md.

### Step 6: Cleanup and Restart

```bash
rm -rf /tmp/git_tracker_install
openclaw restart
```

### Step 7: Verify

```bash
python3 skills/git-tracker/scripts/git_tracker.py --show-config
python3 skills/git-tracker/scripts/git_tracker.py --all --approximate
```

Verify:
- Config shows the correct repositories, num_days, and SSH directory
- Script runs without errors and outputs JSON with `approximate` field
- If issues occur, check `~/git-tracker/config.json` for typos and validate repository URLs

---

## Config Resolution

The script resolves config location in this priority:

1. `GIT_TRACKER_CONFIG_DIR` env var -- explicit override (dev/testing only)
2. `~/git-tracker/` -- default

## File Locations

| Component | Path |
|-----------|------|
| Skill directory | `skills/git-tracker/` |
| Config template | `skills/git-tracker/assets/config.template.json` |
| User config | `~/git-tracker/config.json` |
| Stats data | `~/git-tracker/data/stats_{dd_mm_yyyy}.json` |
| Backups | `~/git-tracker/backups/` |

## Data Persistence Rules

- **During updates:** Only the skill directory is replaced. Config and data at `~/git-tracker/` are untouched.
- **During full install:** Run `--init` or copy template to `~/git-tracker/config.json`, then configure.
- **User Output Format** in SKILL.md: Back up before update, restore after.
