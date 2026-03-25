#!/usr/bin/env python3
"""Git activity tracker - fetches remote git repository data via SSH.

Usage:
    python scripts/git_tracker.py --all --approximate   # Process all repos from config
    python scripts/git_tracker.py --repo <name>         # Process specific repo
    python scripts/git_tracker.py --init                # Create default config
    python scripts/git_tracker.py --show-config         # Show current configuration
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import CalledProcessError, run


# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()

# Resolve config directory:
# 1. GIT_TRACKER_CONFIG_DIR env var (explicit override, dev/testing)
# 2. ~/git-tracker/ (default — outside skill dir for persistence)
_config_env = os.environ.get("GIT_TRACKER_CONFIG_DIR")

if _config_env:
    CONFIG_DIR = Path(_config_env)
else:
    CONFIG_DIR = Path.home() / "git-tracker"

CURRENT_SCHEMA_VERSION = 1


@dataclass
class Repository:
    """Repository configuration."""
    name: str
    ssh_url: str | None = None
    https_url: str | None = None
    branch_name: str | None = None
    user_email: str | None = None

    def get_url(self) -> str:
        """Get the primary URL to use (SSH preferred, then HTTPS)."""
        if self.ssh_url:
            return self.ssh_url
        if self.https_url:
            return self.https_url
        raise ValueError("Repository must have either ssh_url or https_url")

    def is_ssh(self) -> bool:
        """Check if using SSH URL."""
        return bool(self.ssh_url)


@dataclass
class Settings:
    """Application settings."""
    num_days: int = 10


@dataclass
class Config:
    """Main configuration container."""
    repositories: list[Repository]
    settings: Settings
    ssh_dir: Path


DEFAULT_CONFIG = """{
  "_schema_version": 1,
  "repositories": [
    {
      "name": "",
      "ssh_url": "",
      "https_url": "",
      "branch_name": ""
    }
  ],
  "settings": {
    "num_days": 1
  },
  "ssh_dir": "~/.ssh"
}"""


def get_config_path() -> Path:
    """Get the config.json path."""
    return CONFIG_DIR / "config.json"


def get_data_dir() -> Path:
    """Get the data directory for output files."""
    data_dir = CONFIG_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def migrate_config(data: dict) -> dict:
    """Migrate config to current schema version.

    Applies additive migrations in order. Never removes user data.
    """
    version = data.get("_schema_version", 0)

    if version < 1:
        data["_schema_version"] = 1

    return data


def load_config() -> Config:
    """Load configuration from config.json.

    Returns:
        Config object with repository and settings data.

    Raises:
        FileNotFoundError: If config.json doesn't exist.
        json.JSONDecodeError: If config.json is invalid.
    """
    config_path = get_config_path()

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = json.load(f)

    data = migrate_config(data)
    
    repositories = []
    for repo in data.get("repositories", []):
        if not repo.get("ssh_url") and not repo.get("https_url"):
            raise ValueError(f"Repository '{repo.get('name', '<unknown>')}' must have either ssh_url or https_url")

        cleaned_ssh_url = None
        if repo.get("ssh_url"):
            cleaned_ssh_url = repo["ssh_url"].strip()

        cleaned_https_url = None
        if repo.get("https_url"):
            cleaned_https_url = repo["https_url"].strip()
            cleaned_https_url = cleaned_https_url.removeprefix("git clone").strip()

        repositories.append(Repository(
            name=repo["name"],
            ssh_url=cleaned_ssh_url,
            https_url=cleaned_https_url,
            branch_name=repo.get("branch_name"),
            user_email=repo.get("user_email"),
        ))
    
    settings = Settings(
        num_days=data.get("settings", {}).get("num_days", 10)
    )
    
    ssh_dir = Path(data.get("ssh_dir", "~/.ssh")).expanduser()
    
    return Config(
        repositories=repositories,
        settings=settings,
        ssh_dir=ssh_dir,
    )


def get_ssh_key_dir() -> Path:
    """Resolve SSH key directory with priority:
    1. Environment variable: SSH_KEY_DIR
    2. Config: config.ssh_dir
    3. Default: ~/.ssh
    
    Returns:
        Path to SSH key directory.
    """
    # Priority 1: Environment variable
    env_key_dir = os.environ.get("SSH_KEY_DIR")
    if env_key_dir:
        return Path(env_key_dir).expanduser()
    
    # Priority 2: Config file
    try:
        config = load_config()
        return config.ssh_dir
    except FileNotFoundError:
        pass
    
    # Priority 3: Default
    return Path("~/.ssh").expanduser()


def save_default_config() -> None:
    """Save default configuration file if it doesn't exist."""
    config_path = get_config_path()

    if config_path.exists():
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        f.write(DEFAULT_CONFIG)

    # Create data and backups directories
    get_data_dir()
    (CONFIG_DIR / "backups").mkdir(parents=True, exist_ok=True)


def extract_ssh_host(ssh_url: str) -> str:
    """Extract hostname from SSH git URL.

    Handles both formats:
    - git@host:path (e.g., git@github.com:org/repo.git)
    - ssh://git@host/path (e.g., ssh://git@gitlab.com/group/project)

    Args:
        ssh_url: SSH URL of the git repository.

    Returns:
        Hostname extracted from SSH URL.

    Raises:
        ValueError: If SSH URL format is invalid.
    """
    ssh_url = ssh_url.strip().rstrip(".git")

    if ssh_url.startswith("ssh://"):
        host_part = ssh_url[6:].split("/", 2)[0]
    else:
        host_part = ssh_url.split(":")[0]

    if "@" in host_part:
        host = host_part.split("@")[1]
    else:
        host = host_part

    return host


def extract_https_host(https_url: str) -> str:
    """Extract hostname from HTTPS git URL.

    Handles format:
    - https://host/path (e.g., https://github.com/org/repo.git)
    - https://user:token@host/path (e.g., https://x-token-auth:token@bitbucket.org/org/repo.git)
    - git clone https://... (extracts after cleanup)

    Args:
        https_url: HTTPS URL of the git repository.

    Returns:
        Hostname extracted from HTTPS URL.

    Raises:
        ValueError: If HTTPS URL format is invalid.
    """
    url = https_url.strip()

    # Remove 'git clone' prefix if present
    if url.lower().startswith("git clone"):
        url = url[9:].strip()

    # Remove trailing .git
    url = url.rstrip(".git")

    # Remove https://
    if url.startswith("https://"):
        url = url[8:]
    else:
        raise ValueError(f"Invalid HTTPS URL: '{https_url}'. Must start with 'https://'")

    # Extract host (first part before '/')
    host_with_auth = url.split("/")[0]

    # Remove auth credentials if present (user:token@host)
    if "@" in host_with_auth:
        host = host_with_auth.split("@")[1]
    else:
        host = host_with_auth

    return host


def test_ssh_connection(host: str, ssh_key_dir: Path) -> tuple[bool, str]:
    """Test SSH connectivity to a host.

    Runs `ssh -T git@<host>` with retry logic to verify SSH access.

    Args:
        host: Hostname to test (e.g., github.com, gitlab.com).
        ssh_key_dir: Path to SSH key directory.

    Returns:
        Tuple of (success: bool, error_message: str).
        Returns (True, "") on success, (False, error_message) on failure.
    """
    max_attempts = 3
    sleep_between_retries = 2

    for attempt in range(1, max_attempts + 1):
        try:
            ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes", "-T", f"git@{host}"]
            env = os.environ.copy()
            if ssh_key_dir and ssh_key_dir.exists():
                ssh_key = ssh_key_dir / "id_rsa"
                if ssh_key.exists():
                    env["GIT_SSH_COMMAND"] = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -i {ssh_key}"

            result = run(
                ssh_cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=10
            )

            if result.returncode == 0:
                return (True, "")
            elif "permission denied" in result.stderr.lower():
                return (False, "permission denied")
            # GitHub and GitLab return exit code 1 with success messages
            elif "successfully authenticated" in result.stderr.lower() or "welcome to gitlab" in result.stderr.lower():
                return (True, "")
            else:
                error_msg = result.stderr.strip() or "Connection failed"
                return (False, error_msg)

        except subprocess.TimeoutExpired:
            if attempt < max_attempts:
                time.sleep(sleep_between_retries)
                continue
            return (False, "Connection timeout")
        except FileNotFoundError:
            return (False, "SSH command not found")
        except Exception as e:
            error_msg = str(e)
            if attempt < max_attempts:
                time.sleep(sleep_between_retries)
                continue
            return (False, error_msg)

    return (False, "Unknown error")


def test_https_connection(https_url: str) -> tuple[bool, str]:
    """Test HTTPS connectivity to a repository.

    Runs `git ls-remote` to verify repository accessibility via HTTPS.

    Args:
        https_url: HTTPS URL of the git repository.

    Returns:
        Tuple of (success: bool, error_message: str).
        Returns (True, "") on success, (False, error_message) on failure.
    """
    max_attempts = 3
    sleep_between_retries = 2

    ls_env = os.environ.copy()
    ls_env["GIT_TERMINAL_PROMPT"] = "0"

    for attempt in range(1, max_attempts + 1):
        try:
            # Use git ls-remote to test connection without cloning
            cmd = ["git", "ls-remote", "--exit-code", https_url, "HEAD"]

            result = run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                env=ls_env,
            )

            if result.returncode == 0:
                return (True, "")
            else:
                error_msg = result.stderr.strip() or "Connection failed"
                if "authentication failed" in error_msg.lower():
                    return (False, "authentication failed")
                elif "not found" in error_msg.lower():
                    return (False, "repository not found")
                return (False, error_msg)

        except subprocess.TimeoutExpired:
            if attempt < max_attempts:
                time.sleep(sleep_between_retries)
                continue
            return (False, "Connection timeout")
        except FileNotFoundError:
            return (False, "Git command not found")
        except Exception as e:
            error_msg = str(e)
            if attempt < max_attempts:
                time.sleep(sleep_between_retries)
                continue
            return (False, error_msg)

    return (False, "Unknown error")


# =============================================================================
# Git Operations
# =============================================================================


def get_recent_branches(
    git_dir: Path,
    num_days: int,
    exclude_merged: bool = True,
) -> list[str]:
    """Get branches updated within the specified number of days.

    Args:
        git_dir: Path to the .git directory of the repository.
        num_days: Number of days to look back for branch updates.
        exclude_merged: If True, exclude branches that have been merged.

    Returns:
        List of branch names with recent activity.
    """
    now = datetime.now().astimezone()
    cutoff_date = now - timedelta(days=num_days)

    # Get all branches with their last commit dates
    cmd = [
        "git",
        "--git-dir", str(git_dir),
        "for-each-ref",
        "--sort=-committerdate",
        "--format=%(refname:short)|%(committerdate:iso)",
        "refs/heads/",
    ]

    try:
        result = run(cmd, capture_output=True, text=True, check=True)
    except CalledProcessError as e:
        print(f"Warning: Failed to get branches: {e.stderr}", file=sys.stderr)
        return []

    branches: list[str] = []

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        parts = line.split("|")
        if len(parts) < 2:
            continue

        branch_name = parts[0]
        commit_date_str = parts[1]

        try:
            commit_date_str_stripped = commit_date_str.strip()
            # Handle timezone-aware and naive datetimes
            if "+" in commit_date_str_stripped or commit_date_str_stripped.endswith("Z"):
                commit_date = datetime.fromisoformat(commit_date_str_stripped.replace("Z", "+00:00"))
            else:
                commit_date = datetime.fromisoformat(commit_date_str_stripped).astimezone()

            # Check if branch was updated within num_days
            if commit_date >= cutoff_date:
                branches.append(branch_name)
        except (ValueError, IndexError):
            continue

    return branches

@dataclass
class CommitStats:
    """Commit statistics."""
    git_name: str
    username: str
    email: str
    rows_added: int
    rows_removed: int
    spent_time: str
    timestamp: datetime
    branch: str = ""
    error: str = "-"
    approximate: bool = False
    commit_hash: str = ""


def fetch_git_log(
    url: str,
    num_days: int,
    branches: list[str] | None = None,
    user_email: str | None = None,
    ssh_key_dir: Path | None = None,
    is_ssh: bool = True,
    approximate: bool = False,
) -> list[CommitStats]:
    """Fetch git log from remote repository via SSH or HTTPS.

    Args:
        url: URL of the git repository (SSH or HTTPS).
        num_days: Number of days to look back for commits.
        branches: List of branch names to fetch from (None = auto-discover recent branches).
        user_email: Filter by author email (optional).
        ssh_key_dir: Path to SSH key directory (only used for SSH).
        is_ssh: Whether the URL is SSH (True) or HTTPS (False).

    Returns:
        List of CommitStats objects.
    """
    # Create temporary directory for clone
    temp_dir = Path(tempfile.mkdtemp(prefix="git_tracker_"))
    
    try:
        # Configure environment
        clone_env = os.environ.copy()
        clone_env["GIT_TERMINAL_PROMPT"] = "0"

        if is_ssh:
            if ssh_key_dir and ssh_key_dir.exists():
                ssh_key = ssh_key_dir / "id_rsa"
                if ssh_key.exists():
                    clone_env["GIT_SSH_COMMAND"] = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -i {ssh_key}"
                else:
                    clone_env["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes"
            else:
                clone_env["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes"

        # Treeless bare clone — skips blobs, keeps commit history + tree metadata
        # numstat works because line counts are in commit objects, not blobs
        clone_cmd = [
            "git", "clone", "--bare", "--filter=blob:none",
            url, str(temp_dir),
        ]

        try:
            run(clone_cmd, capture_output=True, text=True,
                env=clone_env, check=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Clone timed out after 300s for {url}")
        except CalledProcessError as e:
            raise RuntimeError(f"Failed to clone repository: {e.stderr}") from e

        # Determine which branches to process
        if branches is None:
            branches = get_recent_branches(temp_dir, num_days, exclude_merged=False)

        # If no branches found or specified, use HEAD (all refs)
        if not branches:
            branches = ["HEAD"]

        all_commits: list[CommitStats] = []
        cutoff_date = datetime.now().astimezone() - timedelta(days=num_days)

        since_date = (
            datetime.now().astimezone() - timedelta(days=num_days + 1)
        ).strftime("%Y-%m-%d")

        for branch_name in branches:
            # Fetch git log from cloned repo
            git_format = "%H|%an|%ae|%ad|%s"
            cmd = [
                "git",
                "--git-dir", str(temp_dir),
                "log",
                f"--format={git_format}",
                "--date=iso",
                "--numstat",
                "--no-merges",
                f"--since={since_date}",
            ]

            # Add branch to the command
            cmd.append(branch_name)

            try:
                result = run(cmd, capture_output=True, text=True, check=True)
                commits = _parse_git_log(result.stdout, branch_name, user_email)
                all_commits.extend(commits)
            except CalledProcessError as e:
                print(f"Warning: Failed to fetch log for branch '{branch_name}': {e.stderr}", file=sys.stderr)
                continue

        # Sort all commits by timestamp (ascending)
        all_commits.sort(key=lambda c: c.timestamp)

        # Use wider window for spent_time context, then filter to output window
        context_cutoff = datetime.now().astimezone() - timedelta(days=num_days + 1)
        output_cutoff = datetime.now().astimezone() - timedelta(days=num_days)
        all_commits = [c for c in all_commits if c.timestamp >= context_cutoff]

        # Deduplicate by commit hash (same commit on multiple branches)
        seen: dict[str, CommitStats] = {}
        deduped: list[CommitStats] = []
        for c in all_commits:
            if c.commit_hash in seen:
                seen[c.commit_hash].branch += f", {c.branch}"
            else:
                seen[c.commit_hash] = c
                deduped.append(c)
        all_commits = deduped

        # Reset spent_time from per-branch calculation
        for commit in all_commits:
            commit.spent_time = ""
            commit.approximate = False

        # Fetch one commit before the window for spent_time reference
        prev_timestamp: datetime | None = None
        if all_commits:
            # Subtract 1s so --before excludes the oldest commit itself
            before_ts = (all_commits[0].timestamp - timedelta(seconds=1)).isoformat()
            for branch_name in branches:
                prev_cmd = [
                    "git", "--git-dir", str(temp_dir),
                    "log", "-1", "--format=%ad", "--date=iso",
                    f"--before={before_ts}", "--no-merges",
                    branch_name,
                ]
                try:
                    prev_result = run(prev_cmd, capture_output=True, text=True, check=True)
                    date_str = prev_result.stdout.strip()
                    if date_str:
                        ts = datetime.fromisoformat(date_str)
                        if prev_timestamp is None or ts > prev_timestamp:
                            prev_timestamp = ts
                        break
                except (CalledProcessError, ValueError):
                    continue

        # Calculate spent_time across all commits (chronological order)
        max_workday = timedelta(hours=8)
        for commit in all_commits:
            if prev_timestamp:
                delta = commit.timestamp - prev_timestamp
                if approximate and delta > max_workday:
                    commit.spent_time = _format_delta(max_workday)
                    commit.approximate = True
                else:
                    commit.spent_time = _format_delta(delta)
            prev_timestamp = commit.timestamp

        # Default empty spent_time on first commit (no earlier commit exists)
        if all_commits and not all_commits[0].spent_time:
            all_commits[0].spent_time = "-"

        # Filter to output window (drop the context day)
        all_commits = [c for c in all_commits if c.timestamp >= output_cutoff]

        # Reverse to newest-first for output
        all_commits.reverse()

        return all_commits

    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def _parse_git_log(output: str, branch_name: str, user_email: str | None) -> list[CommitStats]:
    """Parse git log output into CommitStats objects.

    Git log output format (--numstat):
    hash|Author Name|email@domain.com|timestamp|Subject
    <added>\t<removed>\t<filename>    # one or more lines per commit
    <added>\t<removed>\t<filename>
    hash2|Author Name2|email2@domain.com|timestamp2|Subject2
    ...
    """
    # First pass: parse all commits without calculating spent_time
    commits_without_time: list[dict] = []
    lines = output.strip().split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this is a commit header line (contains '|')
        if "|" in line:
            parts = line.split("|")
            if len(parts) < 5:
                i += 1
                continue

            commit_hash = parts[0]
            git_name = parts[1]
            email = parts[2]
            timestamp_str = parts[3]

            # Filter by user_email if specified
            if user_email and email != user_email:
                # Skip this commit entirely - move past all numstat lines
                i += 1
                while i < len(lines) and "|" not in lines[i]:
                    i += 1
                continue

            username = email.split("@")[0] if "@" in email else email
            timestamp_str_stripped = timestamp_str.strip()
            # Handle timezone-aware and naive datetimes
            if "+" in timestamp_str_stripped or timestamp_str_stripped.endswith("Z"):
                timestamp = datetime.fromisoformat(timestamp_str_stripped.replace("Z", "+00:00"))
            else:
                timestamp = datetime.fromisoformat(timestamp_str_stripped).astimezone()

            # Parse all numstat lines for this commit
            rows_added = 0
            rows_removed = 0
            i += 1

            while i < len(lines) and "|" not in lines[i]:
                numstat_line = lines[i]
                if numstat_line and "\t" in numstat_line:
                    try:
                        added, removed = numstat_line.split("\t")[:2]
                        if added != "-":
                            rows_added += int(added)
                        if removed != "-":
                            rows_removed += int(removed)
                    except (ValueError, IndexError):
                        pass
                i += 1

            commits_without_time.append({
                "commit_hash": commit_hash,
                "git_name": git_name,
                "username": username,
                "email": email,
                "rows_added": rows_added,
                "rows_removed": rows_removed,
                "timestamp": timestamp,
                "branch": branch_name,
            })
        else:
            i += 1

    # Reverse commits to chronological order (oldest first)
    # This ensures positive time deltas between consecutive commits
    commits_without_time.reverse()

    # Second pass: calculate spent_time in chronological order
    commits: list[CommitStats] = []
    prev_timestamp: datetime | None = None

    for commit_data in commits_without_time:
        timestamp = commit_data["timestamp"]
        spent_time = ""
        if prev_timestamp:
            delta = timestamp - prev_timestamp
            spent_time = _format_delta(delta)

        prev_timestamp = timestamp

        commits.append(CommitStats(
            git_name=commit_data["git_name"],
            username=commit_data["username"],
            email=commit_data["email"],
            rows_added=commit_data["rows_added"],
            rows_removed=commit_data["rows_removed"],
            spent_time=spent_time,
            timestamp=timestamp,
            branch=commit_data["branch"],
            commit_hash=commit_data["commit_hash"],
        ))

    return commits


def _format_delta(delta: timedelta) -> str:
    """Format timedelta into <XdXhXm> format string.
    
    Args:
        delta: Time difference between commits.
    
    Returns:
        String in format "<days>d<hours>h<minutes>m".
        Example: 172800 seconds returns "2d0h0m".
    """
    total_seconds = int(abs(delta.total_seconds()))
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{days}d{hours}h{minutes}m"


def write_stats(commits: list[CommitStats], output_file: Path) -> None:
    """Write commit statistics to local file.
    
    Args:
        commits: List of CommitStats to write.
        output_file: Path to output file.
    """
    data = [
        {
            "commit_hash": c.commit_hash,
            "git_name": c.git_name,
            "username": c.username,
            "email": c.email,
            "rows_added": c.rows_added,
            "rows_removed": c.rows_removed,
            "spent_time": c.spent_time,
            "timestamp": c.timestamp.isoformat(),
            "branch": c.branch,
            "error": c.error,
            "approximate": c.approximate,
        }
        for c in commits
    ]
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)


def get_last_n_rows(output_file: Path, n: int = 10) -> list[dict]:
    """Read last n rows from statistics file.
    
    Args:
        output_file: Path to statistics file.
        n: Number of rows to return.
    
    Returns:
        List of commit statistics dictionaries.
    """
    if not output_file.exists():
        return []
    
    with open(output_file) as f:
        data = json.load(f)
    
    return data[-n:]


def get_stats_output_filename() -> Path:
    """Get daily statistics output filename.

    Returns:
        Path to stats file with format: stats_{dd_mm_yyyy}.json
    """
    today = datetime.now().strftime("%d_%m_%Y")
    return get_data_dir() / f"stats_{today}.json"


# =============================================================================
# Processing
# =============================================================================

def process_repository(
    repo: Repository,
    num_days: int,
    ssh_key_dir: Path | None = None,
    approximate: bool = False,
) -> list[CommitStats]:
    """Process a single repository.

    Args:
        repo: Repository configuration.
        num_days: Number of days to look back for commits.
        ssh_key_dir: Path to SSH key directory (only used for SSH).

    Returns:
        List of commit statistics.
    """
    print(f"Processing repository: {repo.name}")

    url = repo.get_url()
    is_ssh = repo.is_ssh()

    # Test connection based on URL type
    if is_ssh:
        print(f"  SSH URL: {url}")
        host = extract_ssh_host(url)
        success, error_msg = test_ssh_connection(host, ssh_key_dir if ssh_key_dir else get_ssh_key_dir())
    else:
        print(f"  HTTPS URL: {url}")
        success, error_msg = test_https_connection(url)

    print(f"  Using num_days: {num_days}")

    if not success:
        print(f"  Connection test failed: {error_msg}")
        error_entry = CommitStats(
            git_name="",
            username="",
            email="",
            rows_added=0,
            rows_removed=0,
            spent_time="",
            timestamp=datetime.now().astimezone(),
            error=error_msg,
        )
        return [error_entry]

    commits = fetch_git_log(
        url=url,
        num_days=num_days,
        branches=[repo.branch_name] if repo.branch_name else None,
        user_email=repo.user_email,
        ssh_key_dir=ssh_key_dir if ssh_key_dir and is_ssh else (get_ssh_key_dir() if is_ssh else None),
        is_ssh=is_ssh,
        approximate=approximate,
    )

    return commits


def process_all_repos(config: Config, num_days: int | None = None, approximate: bool = False) -> dict[str, list[dict]]:
    """Process all repositories from config.

    Args:
        config: Configuration object.
        num_days: Number of days to look back (None = use config setting).

    Returns:
        Dictionary mapping repo names to their commits.
    """
    ssh_key_dir = get_ssh_key_dir()
    results = {}

    # Use CLI argument if provided, otherwise use config setting
    days_to_use = num_days if num_days is not None else config.settings.num_days

    for repo in config.repositories:
        try:
            commits = process_repository(
                repo=repo,
                num_days=days_to_use,
                ssh_key_dir=ssh_key_dir,
                approximate=approximate,
            )
            # Convert to dict for JSON serialization
            results[repo.name] = [
                {
                    "commit_hash": c.commit_hash,
                    "git_name": c.git_name,
                    "username": c.username,
                    "email": c.email,
                    "rows_added": c.rows_added,
                    "rows_removed": c.rows_removed,
                    "spent_time": c.spent_time,
                    "timestamp": c.timestamp.isoformat(),
                    "branch": c.branch,
                    "error": "-",
                    "approximate": c.approximate,
                }
                for c in commits
            ]
        except Exception as e:
            error_message = str(e)
            print(f"Error processing {repo.name}: {error_message}", file=sys.stderr)
            results[repo.name] = [
                {
                    "git_name": "",
                    "username": "",
                    "email": "",
                    "rows_added": 0,
                    "rows_removed": 0,
                    "spent_time": "",
                    "timestamp": "",
                    "branch": "",
                    "error": error_message,
                }
            ]

    daily_file = get_stats_output_filename()
    all_entries = []

    for repo_name, repo_data in results.items():
        all_entries.extend(repo_data)

    with open(daily_file, "w") as f:
        json.dump(all_entries, f, indent=2)

    print(f"  All results written to: {daily_file}")

    return results


def init_config() -> None:
    """Initialize default configuration."""
    save_default_config()
    print(f"Created default config at: {get_config_path()}")
    print("Please edit config.json to add repositories.")


# =============================================================================
# Main
# =============================================================================

def main() -> dict[str, list[dict]]:
    """Main entry point for git tracker.
    
    Returns:
        Dictionary mapping repo names to their commit statistics.
    """
    parser = argparse.ArgumentParser(
        description="Track git activity from remote repositories via SSH."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all repositories from config",
    )
    parser.add_argument(
        "--repo",
        type=str,
        help="Process specific repository by name",
    )
    parser.add_argument(
        "--num-days",
        type=int,
        default=None,
        help="Number of days to look back (default: from config)",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create default config.json",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show current configuration",
    )
    parser.add_argument(
        "--approximate",
        action="store_true",
        help="Cap spent_time at 8h workday, flag approximate entries",
    )
    
    args = parser.parse_args()
    
    # Handle init
    if args.init:
        init_config()
        return {}
    
    # Handle show-config
    if args.show_config:
        try:
            config = load_config()
            print(f"Config path: {get_config_path()}")
            print(f"Data dir: {get_data_dir()}")
            print(f"SSH key dir: {get_ssh_key_dir()}")
            print(f"Repositories ({len(config.repositories)}):")
            for repo in config.repositories:
                print(f"  - {repo.name}: {repo.ssh_url or repo.https_url}")
            print(f"Default num_days: {config.settings.num_days}")
        except FileNotFoundError:
            print("No config found. Run --init to create one.")
        return {}
    
    # Load config
    try:
        config = load_config()
    except FileNotFoundError:
        print("Error: config.json not found.", file=sys.stderr)
        print("Run: git_tracker.py --init", file=sys.stderr)
        sys.exit(1)
    
    # Process repos
    if args.all:
        return process_all_repos(config, args.num_days, approximate=args.approximate)
    elif args.repo:
        # Find specific repo
        repo = next((r for r in config.repositories if r.name == args.repo), None)
        if repo is None:
            print(f"Error: Repository '{args.repo}' not found in config.", file=sys.stderr)
            sys.exit(1)

        ssh_key_dir = get_ssh_key_dir()
        commits = process_repository(
            repo=repo,
            num_days=args.num_days,
            ssh_key_dir=ssh_key_dir,
            approximate=args.approximate,
        )
        return {
            repo.name: [
                {
                    "commit_hash": c.commit_hash,
                    "git_name": c.git_name,
                    "username": c.username,
                    "email": c.email,
                    "rows_added": c.rows_added,
                    "rows_removed": c.rows_removed,
                    "spent_time": c.spent_time,
                    "timestamp": c.timestamp.isoformat(),
                    "branch": c.branch,
                    "approximate": c.approximate,
                }
                for c in commits
            ]
        }
    else:
        parser.print_help()
        return {}


if __name__ == "__main__":
    result = main()
    if result:
        print(json.dumps(result, indent=2))
