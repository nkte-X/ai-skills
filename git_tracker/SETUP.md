# Git Tracker Skill – Setup Manual

This document describes how to install or update the **git-tracker** skill on an OpenClaw instance.

## Prerequisites

- Access to the OpenClaw instance filesystem
- `OPENCLAW_WORKSPACE_DIR` set to the OpenClaw workspace (`~/.openclaw/workspace/` by default)
- Python 3.9+, git CLI installed

**Source repository:** `https://github.com/nkte-X/ai-skills.git` (branch: master)

---

## Detect Install vs Update

```bash
if [ -d "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker" ]; then
    echo "Skill found. Performing UPDATE..."
    # → go to Update Procedure
else
    echo "Skill not found. Performing FULL INSTALL..."
    # → go to Full Installation
fi
```

---

## Update Procedure

Use this when the skill is already installed and you want to pull the latest version.

### 1. Clone latest source

```bash
cd /tmp && git clone https://github.com/nkte-X/ai-skills.git git_tracker_update
```

### 2. Backup User Output Format

Copy the text between `## User Output Format` and the next `##` heading from the current SKILL.md — this contains user-specific preferences that must be preserved.

### 3. Update files

```bash
# Update skill directory (SKILL.md, scripts/, references/)
cp -r /tmp/git_tracker_update/git_tracker/git-tracker/ "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker"
```

### 4. Restore User Output Format

Paste the backed-up preferences into the new SKILL.md, replacing `[USER_PREFERENCES_HERE]`.

### 5. NEVER overwrite

- `${OPENCLAW_WORKSPACE_DIR}/git_tracker/config.json` — user-specific repository configuration
- `${OPENCLAW_WORKSPACE_DIR}/git_tracker/data/` — accumulated statistics

### 6. Cleanup and restart

```bash
rm -rf /tmp/git_tracker_update
openclaw restart
```

### 7. Verify

```bash
python3 ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/scripts/git_tracker.py --show-config
python3 ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/scripts/git_tracker.py --all --approximate
```

---

## Full Installation

### Step 1: Clone Repository

```bash
cd ${OPENCLAW_WORKSPACE_DIR}
git clone https://github.com/nkte-X/ai-skills.git CLONE_DIR
```

### Step 2: Copy Skill Directory

```bash
cp -r CLONE_DIR/git_tracker/git-tracker/ "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker"
```

This copies SKILL.md, scripts/git_tracker.py, and references/ into the skills workspace. The script runs directly from the skill directory.

### Step 3: Copy Config and Data Module

```bash
cp -r CLONE_DIR/git_tracker/git_tracker/ ${OPENCLAW_WORKSPACE_DIR}/git_tracker/
```

This creates:
- `${OPENCLAW_WORKSPACE_DIR}/git_tracker/config-example.json` — example config template
- `${OPENCLAW_WORKSPACE_DIR}/git_tracker/data/` — daily statistics storage

### Step 4: Create Config from Example

```bash
cp ${OPENCLAW_WORKSPACE_DIR}/git_tracker/config-example.json ${OPENCLAW_WORKSPACE_DIR}/git_tracker/config.json
```

### Step 5: Configure Tracked Repositories

Ask the user to provide for each repository:
- **Repository URL** — SSH (`git@github.com:org/repo.git`) or HTTPS (`https://github.com/org/repo.git`)
- **Custom name** — a display name for the repository (e.g., "backend", "staging")
- **Branch** — specific branch to track, or leave blank to auto-discover all recent branches

Write to `${OPENCLAW_WORKSPACE_DIR}/git_tracker/config.json`:
- URL goes to `ssh_url` or `https_url` based on format
- Custom name goes to `name`
- Branch goes to `branch_name` (blank = all branches)

Ask the user how many days back to track and write to `settings.num_days`.

Example config:
```json
{
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

### Step 6: Set Up User Output Format

Read the SKILL.md file. If the "User Output Format" section shows `[USER_PREFERENCES_HERE]`, ask the user:

1. **Output format** — Markdown table / JSON / CSV / Custom
2. **Date format** — DD.MM.YYYY / DD-MM-YY / YYYY-MM-DD / Custom
3. **Author display** — Username (email prefix) / Full name / Email / Custom

Write their choices into the "User Output Format" section of SKILL.md with a concrete template. Example:

```markdown
## User Output Format

**Output Format:** Markdown table
**Date Format:** DD.MM.YYYY
**Author Format:** Username (email prefix)

**Template:**
| date | repo | +lines | -lines | author | branch | time spent |
|------|------|--------|--------|--------|--------|------|
| {DD.MM.YYYY} | {repo_name} | +{rows_added} | -{rows_removed} | {username} | {branch} | {spent_time_formatted} |
```

### Step 7: Cleanup

```bash
cd ${OPENCLAW_WORKSPACE_DIR}
rm -rf CLONE_DIR
```

### Step 8: Restart OpenClaw

```bash
openclaw restart
```

### Step 9: Verify

```bash
python3 ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/scripts/git_tracker.py --show-config
python3 ${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/scripts/git_tracker.py --all --approximate
```

Verify:
- Config shows the correct repositories, num_days, and SSH directory
- Script runs without errors and outputs JSON with `approximate` field
- If issues occur, check config.json for typos and validate repository URLs

---

## File Locations

| File | Source | Destination |
|------|--------|-------------|
| Skill directory (incl. scripts/) | `CLONE_DIR/git_tracker/git-tracker/` | `${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/` |
| Config example | `CLONE_DIR/git_tracker/git_tracker/config-example.json` | `${OPENCLAW_WORKSPACE_DIR}/git_tracker/config-example.json` |
| Config & data | `CLONE_DIR/git_tracker/git_tracker/` | `${OPENCLAW_WORKSPACE_DIR}/git_tracker/` |

## Data Persistence Rules

- **During updates:** Always preserve `config.json`, `data/`, and "User Output Format" in SKILL.md
- **During full install:** Copy `config-example.json` → `config.json`, then configure with user
- **Daily stats:** Stored as `${OPENCLAW_WORKSPACE_DIR}/git_tracker/data/stats_{dd_mm_yyyy}.json`
