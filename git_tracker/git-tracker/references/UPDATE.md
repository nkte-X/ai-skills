# Skill Update Procedure

Source repository: `https://github.com/nkte-X/ai-skills.git` (branch: master)

## Steps

1. **Clone latest from source:**
   ```bash
   cd /tmp && git clone https://github.com/nkte-X/ai-skills.git git_tracker_update
   ```

2. **Backup current User Output Format section** from SKILL.md (copy the text between `## User Output Format` and the next `##` heading)

3. **Update skill directory (SKILL.md, scripts/, references/):**
   ```bash
   cp -r /tmp/git_tracker_update/git_tracker/git-tracker/ OPENCLAW_WORKSPACE_DIR/skills/git-tracker
   ```

4. **Restore User Output Format section** — paste the backed-up preferences into the new SKILL.md, replacing `[USER_PREFERENCES_HERE]`

5. **NEVER overwrite:**
   - `ROOT_DIR/git_tracker/config.json` — user-specific repository configuration
   - `ROOT_DIR/git_tracker/data/` — accumulated statistics

6. **Cleanup and restart:**
   ```bash
   rm -rf /tmp/git_tracker_update
   openclaw restart
   ```
