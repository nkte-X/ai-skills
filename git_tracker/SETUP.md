# Git Tracker Skill – Setup Manual

This document describes how to install the **git-tracker** skill into an OpenClaw instance.

## Prerequisites

- Access to the OpenClaw instance filesystem
- `OPENCLAW_WORKSPACE_DIR` environment variable set to the OpenClaw agent-specific workspace (`~/.openclaw/workspace/` by default)
- `ROOT_DIR` is the execution OpenClaw root directory (set the environment variable)
- Git repository URL for the git-tracker skill

## Setup Workflow

The setup process follows these steps:

1. **Check for existing installation** → Update or full install
2. **Clone repository** → Extract files
3. **Copy files to target locations**
4. **Configure user output format preferences**
5. **Clean up and restart**

---

## Step 0: Check for Existing Installation

Before performing a full installation, check if the skill is already installed:

```bash
if [ -d "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker" ]; then
    echo "Skill already installed. Performing update operation..."
    # Proceed to update workflow
else
    echo "Skill not found. Performing full installation..."
    # Proceed to full installation workflow
fi
```

### Update Operation (If Skill Already Exists)

**If the skill is already installed:**

1. **PRESERVE user data:**
   - Keep `ROOT_DIR/git_tracker/config.json` unchanged
   - Keep `ROOT_DIR/git_tracker/data/` directory unchanged
   - Keep "User Output Format" section in SKILL.md unchanged

2. **Update Python script:**
   ```bash
   cp CLONE_DIR/script/git_tracker.py ROOT_DIR/scripts/
   ```

3. **Update skill file:**
   ```bash
   # Extract existing User Output Format section before overwriting
   EXISTING_FORMAT=$(grep -A 20 "^## User Output Format$" "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/SKILL.md")
   
   # Copy new skill file
   cp CLONE_DIR/git-tracker/SKILL.md "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/SKILL.md"
   
   # Restore User Output Format section
   # (Use sed/awk for precise replacement in production)
   ```

4. **Skip steps 3-7** (config and data already exist, no need to ask preferences)

5. **Proceed to Step 8: Restart OpenClaw**

---

## Full Installation (If Skill Not Installed)

### Step 1: Clone Repository

Clone the git-tracker repository to ROOT_DIR:

```bash
cd ROOT_DIR
git clone <repository-url> CLONE_DIR
```

Where `<repository-url>` is the git repository URL for the git-tracker skill.

---

### Step 2: Extract and Copy Skill File

Copy the skill definition to the OpenClaw skills workspace:

```bash
mkdir -p "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker"
cp CLONE_DIR/git-tracker/SKILL.md "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/SKILL.md"
```

---

### Step 3: Extract and Copy Python Script

Copy the main Python script to the OpenClaw scripts directory:

```bash
mkdir -p ROOT_DIR/scripts
cp CLONE_DIR/script/git_tracker.py ROOT_DIR/scripts/
```

---

### Step 4: Copy git_tracker Module with Config and Data

Copy the git_tracker directory (containing config and data subdirectories) to ROOT_DIR:

```bash
cp -r CLONE_DIR/git_tracker/ ROOT_DIR/
```

This creates:
- `ROOT_DIR/git_tracker/config.json` (git_tracker.py script configuration)
- `ROOT_DIR/git_tracker/data/` (daily statistics storage)

---

### Step 5: Set Up User Output Format Preferences

Ask the user for their output format preferences and update the skill file:

#### Question 1: Output Data Format

```
What format would you like to use for displaying git tracker statistics?

Options:
1. Markdown table
2. JSON format
3. CSV format
4. Custom format (please specify)

Examples:

Markdown table:
| date | repo_name | rows_added | rows_removed | username | branch | spent_time |
|------|-----------|------------|--------------|----------|--------|------------|
| 06.03.2026 | backend | +70 | -20 | Alex | main | 0d2h30m |

JSON format:
[{"date": "06.03.2026", "repo_name": "backend", "rows_added": 70, "rows_removed": 20, "username": "Alex", "branch": "main", "spent_time": "2h30m"}]

CSV format:
date,repo_name,rows_added,rows_removed,username,branch,spent_time
06.03.2026,backend,+70,-20,Alex,main,0d2h30m
```

#### Question 2: Date Format

```
What date format do you prefer?

Options:
1. DD-MM-YYYY
2. DD-MM-YY
3. YYYY-MM-DD
4. Custom format (please specify)

Examples:
DD-MM-YYYY: 06-03-2026
DD-MM-YY: 06-03-26
YYYY-MM-DD: 2026-03-06
```

#### Question 3: Author Name Format

```
How should the commit author be displayed?

Options:
1. Username (email prefix before @)
2. Full name
3. Email address
4. Custom format (please specify)

Examples (for "john.doe@company.com"):
Username: john.doe
Full name: John Doe (from git commit)
Email: john.doe@company.com
```

---

### Step 6: Update SKILL.md with User Preferences

After the user selects their preferences, update the skill file:

1. **Read the skill file:**
   ```bash
   SKILL_FILE="${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/SKILL.md"
   ```

2. **Locate the "User Output Format" section** (replace placeholder content)

3. **Update the section with user preferences:**

   Example output for Markdown table + DD-MM-YYYY + Username:

   ```markdown
   ## User Output Format

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
   - rows_added: rows_added with + prefix
   - rows_removed: rows_removed with - prefix
   - username: email prefix (before @)
   - branch: branch name from commit
   - spent_time: approximate time spent based on spent_time field
   ```

4. **Save the updated skill file**

---

### Step 7: Delete Cloned Repository

Remove the temporary cloned repository directory:

```bash
cd ROOT_DIR
rm -rf CLONE_DIR
```

---

### Step 8: Set Up tracked git repository

#### From the ROOT_DIR run script with --init flag
```bash
cd ROOT_DIR
python3 ./scripts/git-tracker.py --init
```

#### Ask user too provide trackable repository link, custom name or repository (for exampe staging) , if there is specific required branch to track or all
- write it to ROOT_DIR/git_tracker/config.json 
   - to `ss_url` or `https_url` based on url format
   - custom name to `name`
   - if user wants to track all branches - keep `branch` blank, otherwise add field
#### Ask user how many days back to track
- write value to ROOT_DIR/git_tracker/config.json -> num_days

### Step 9: Restart OpenClaw

Restart the OpenClaw service using the native restart command so it picks up the newly installed/updated skill.

> **Note:** If OpenClaw is managed differently on your system (e.g., a Docker container or a custom init script), use the appropriate restart command for your setup.

---

### Step 10: Run the script with --show-config flag to verify if setup was correct
```bash
cd ROOT_DIR
python3 ./scripts/git-tracker.py --show-config
```
- if there is some issue or config is not shown ask your to validate config and show him file

## Summary of File Locations

| File | Source | Destination |
|------|--------|-------------|
| Skill definition | `CLONE_DIR/git-tracker/SKILL.md` | `${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/SKILL.md` |
| Python script | `CLONE_DIR/script/git_tracker.py` | `ROOT_DIR/scripts/git_tracker.py` |
| Config & data | `CLONE_DIR/git_tracker/` | `ROOT_DIR/git_tracker/` |

---

## Data Persistence Rules

- **During updates:** Always preserve `ROOT_DIR/git_tracker/config.json` and `ROOT_DIR/git_tracker/data/`
- **During updates:** Always preserve the "User Output Format" section in the skill file
- **During full install:** Initial config.json will be created when the script runs `--init`
- **Data files:** Daily statistics are stored as `ROOT_DIR/git_tracker/data/stats_{dd_mm_yyyy}.json`
