# Git Tracker Skill – Setup Manual

This document describes how to install the **git-tracker** skill into an OpenClaw instance.

## Prerequisites

- Access to the OpenClaw instance filesystem
- `OPENCLAW_WORKSPACE_DIR` environment variable set to the OpenClaw workspace root (e.g. `/opt/openclaw/workspace`)
- The `ai-skills/` repository cloned on the target system

## Installation Steps

### 1. Recursively copy `git-tracker/` to the skills workspace

Copy the skill definition folder into the OpenClaw skills directory so that OpenClaw can discover and load the skill.

```bash
cp -r git_tracker/git-tracker/ "${OPENCLAW_WORKSPACE_DIR}/skills/git-tracker/"
```

### 2. Copy scripts to `{rootdir}/scripts`

Copy the Python helper script to the OpenClaw root scripts directory.

```bash
mkdir -p "${OPENCLAW_ROOT_DIR}/scripts"
cp git_tracker/script/git_tracker.py "${OPENCLAW_ROOT_DIR}/scripts/"
```

> `OPENCLAW_ROOT_DIR` is the root directory of the OpenClaw installation (one level above the workspace).

### 3. Recursively copy `git_tracker/` to `{rootdir}`

Copy the full tracker module (config, data directory, etc.) to the OpenClaw root directory so the script can find its configuration at runtime.

```bash
cp -r git_tracker/git_tracker/ "${OPENCLAW_ROOT_DIR}/"
```

### 4. Delete the `ai-skills/` folder

Once all files have been copied to their target locations, remove the cloned repository directory to keep the filesystem clean.

```bash
rm -rf ai-skills/
```

### 5. Restart the OpenClaw instance

Restart the OpenClaw service so it picks up the newly installed skill.

```bash
systemctl restart openclaw
```

> If OpenClaw is managed differently on your system (e.g. a Docker container or a custom init script), use the appropriate restart command instead.

## Automated Installation

The steps above are automated by the provided `setup.bash` script. Run it from inside the cloned `ai-skills/` directory:

```bash
OPENCLAW_WORKSPACE_DIR=/path/to/workspace bash git_tracker/setup.bash
```

The script will perform all five steps and print a summary of installed files on success.
