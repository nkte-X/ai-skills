# Skill Update Procedure

Source repository: `https://github.com/nkte-X/ai-skills.git` (branch: master)

## Steps

1. **Clone latest from source:**
   ```bash
   cd /tmp && git clone https://github.com/nkte-X/ai-skills.git git_tracker_update
   ```

2. **Backup current User Output Format section** from `skills/git-tracker/SKILL.md` (copy the text between `## User Output Format` and the next `##` heading)

3. **Update skill directory (SKILL.md, scripts/, references/, assets/):**
   ```bash
   cp -r /tmp/git_tracker_update/git_tracker/git-tracker/* skills/git-tracker/
   ```

4. **Restore User Output Format section** -- paste the backed-up preferences into the new SKILL.md, replacing `[USER_PREFERENCES_HERE]`

5. **Config and data are safe** -- they live at `~/git-tracker/` (outside the skill directory) and are not affected by updates.

6. **Cleanup and restart:**
   ```bash
   rm -rf /tmp/git_tracker_update
   openclaw restart
   ```

7. **Verify:**
   ```bash
   python3 skills/git-tracker/scripts/git_tracker.py --show-config
   python3 skills/git-tracker/scripts/git_tracker.py --all --approximate
   ```
