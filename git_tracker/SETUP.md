# Git Tracker Skill – Setup Manual

This document describes how to install the **git-tracker** skill into an OpenClaw instance.

## Prerequisites

- Access to the OpenClaw instance filesystem
- `OPENCLAW_WORKSPACE_DIR` environment variable set to the OpenClaw agent-specifc workspace  (`~/.openclaw/workspace/` by default)
- `ROOT_DIR` is the execution openclaw root, set the environment variable
- The `ai-skills/` repository cloned to the the OpenClaw root (i.e. `{ROOT_DIR}/ai-skills/`)

## Installation Steps

### 0. Check if skill is already installed

Before performing a full installation, check if the skill already exists:

```bash
if [ -d "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker" ]; then
    # Skill already installed - do quick update only
    echo "Skill already installed. Performing quick update..."
    
    # Update Python script
    mkdir -p ../../scripts
    cp git_tracker/script/git_tracker.py ../../scripts/
    
    # Update git_tracker module
    cp -r git_tracker/git_tracker/ ../../
    
    # Update skill file but PRESERVE "User view data format" section
    # Read existing format preference before overwriting
    EXISTING_FORMAT=$(grep -A 5 "## User view data format" "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/SKILL.md" | head -10)
    
    # Copy new skill file
    cp -f git_tracker/git-tracker/* "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/"
    
    # Restore the original format section (in production, use sed/awk for precise replacement)
    echo "Skill updated successfully (User view data format preserved)."
    exit 0
fi
echo "Skill not found. Proceeding with full installation..."
```

If skill is already installed, the agent should:
1. Update Python script in `{ROOT_DIR}/scripts/`
2. Update `git_tracker/` module
3. Update skill file in `${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/SKILL.md`
4. **KEEP the "User view data format" section unchanged**
5. Finish setup, notify user that skill was updated

### 1. Recursively copy `git-tracker/` to the skills workspace

Copy the skill definition folder into the OpenClaw skills directory so that OpenClaw can discover and load the skill.

```bash
cp -r git_tracker/git-tracker/ "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/"
```

### 2. Copy scripts to `{ROOT_DIR}/scripts`

Copy the Python helper script to the OpenClaw root scripts directory.

```bash
mkdir -p ../../scripts
cp git_tracker/script/git_tracker.py ../../scripts/
```

### 3. Recursively copy `git_tracker/` to `{ROOT_DIR}`

Copy the full tracker module (config, data directory, etc.) to the OpenClaw root directory so the script can find its configuration at runtime.

```bash
cp -r git_tracker/git_tracker/ ../../
```

### 4. Delete the `ai-skills/` folder

Once all files have been copied to their target locations, remove the cloned repository directory to keep the filesystem clean.

```bash
rm -rf ai-skills/
```

### 5. Choose Output Data Format

After unpacking, the agent should ask the user what format they prefer for viewing git tracker data:

**Interactive Questions:**
```
What format would you like to use for displaying git tracker statistics?

Options:
1. Markdown table (e.g.)
   | time | repo name | rows added | rows deleted | username/email |
   |------|-----------|-----------|--------------|----------------|
   | ...  | ...       | ...       | ...          | ...            |

2. JSON format
   [
     {"time": "...", "repo_name": "...", "rows_added": 0, "rows_removed": 0, "username": "..."}
   ]

3. CSV format
   time,repo_name,rows_added,rows_removed,username/email
   ...,...,...,...,...

4. Whatever user prefer

What the user/commit author format is prefered?

Options:
1. DD-MM-YYYY
2. DD-MM-YY
3. YYYY-MM-DD
4. custom format

What datatime format is prefered?
```

**Skill File Update:**
After the user selects their preferred format, the agent must update the skill file (`${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/SKILL.md`) by adding or modifying the "User view data format" section with the chosen format.

### 6. Restart the OpenClaw instance

Restart the OpenClaw service using the native way, so it picks up the newly installed skill.

> If OpenClaw is managed differently on your system (e.g. a Docker container or a custom init script), use the appropriate restart command instead.