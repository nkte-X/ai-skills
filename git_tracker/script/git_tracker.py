#!/usr/bin/env python3
"""Git activity tracker - fetches remote git repository data via SSH.

Usage:
    python script/git_tracker.py --all              # Process all repos from config
    python script/git_tracker.py --repo <name>     # Process specific repo
    python script/git_tracker.py --init            # Create default config
    python script/git_tracker.py --show-config     # Show current configuration
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
CONFIG_DIR = SCRIPT_DIR.parent / "git_tracker"


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
    num_commit: int = 10


@dataclass
class Config:
    """Main configuration container."""
    repositories: list[Repository]
    settings: Settings
    ssh_dir: Path


DEFAULT_CONFIG = """{
  "repositories": [],
  "settings": {
    "num_commit": 10
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
        num_commit=data.get("settings", {}).get("num_commit", 10)
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
    
    with open(config_path, "w") as f:
        f.write(DEFAULT_CONFIG)
    
    # Create data directory
    get_data_dir()


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

    for attempt in range(1, max_attempts + 1):
        try:
            # Use git ls-remote to test connection without cloning
            cmd = ["git", "ls-remote", "--exit-code", https_url, "HEAD"]
            
            result = run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
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
    error: str = "-"


def fetch_git_log(
    url: str,
    num_commits: int = 10,
    branch: str | None = None,
    user_email: str | None = None,
    ssh_key_dir: Path | None = None,
    is_ssh: bool = True,
) -> list[CommitStats]:
    """Fetch git log from remote repository via SSH or HTTPS.
    
    Args:
        url: URL of the git repository (SSH or HTTPS).
        num_commits: Number of recent commits to fetch.
        branch: Branch name to fetch from (None = default branch).
        user_email: Filter by author email (optional).
        ssh_key_dir: Path to SSH key directory (only used for SSH).
        is_ssh: Whether the URL is SSH (True) or HTTPS (False).
    
    Returns:
        List of CommitStats objects.
    """
    # Create temporary directory for clone
    temp_dir = Path(tempfile.mkdtemp(prefix="git_tracker_"))
    
    try:
        # Clone repository
        clone_cmd = ["git", "clone", "--bare", url, str(temp_dir)]

        # Configure environment based on URL type
        clone_env = os.environ.copy()
        
        if is_ssh:
            # Use custom SSH key if provided
            if ssh_key_dir and ssh_key_dir.exists():
                ssh_key = ssh_key_dir / "id_rsa"
                if ssh_key.exists():
                    clone_env["GIT_SSH_COMMAND"] = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -i {ssh_key}"
                else:
                    clone_env["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes"
            else:
                clone_env["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes"
        # For HTTPS, use default environment (no special SSH configuration)

        try:
            clone_result = run(clone_cmd, capture_output=True, text=True, env=clone_env, check=True)
        except CalledProcessError as e:
            raise RuntimeError(f"Failed to clone repository: {e.stderr}") from e
        
        # Fetch git log from cloned repo
        # Fetch num_commits + 1 to account for the oldest commit having no previous timestamp
        git_format = "%an|%ae|%ad|%s"
        cmd = [
            "git",
            "--git-dir", str(temp_dir),
            "log",
            f"--format={git_format}",
            f"-{num_commits + 1}",
            "--date=iso",
            "--numstat",
        ]
        
        if branch:
            cmd.append(branch)
        
        try:
            result = run(cmd, capture_output=True, text=True, check=True)
        except CalledProcessError as e:
            raise RuntimeError(f"Failed to fetch git log: {e.stderr}") from e
        
        return _parse_git_log(result.stdout, num_commits, user_email)
    
    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def _parse_git_log(output: str, num_commits: int, user_email: str | None) -> list[CommitStats]:
    """Parse git log output into CommitStats objects.
    
    Git log output format (--numstat):
    Author Name|email@domain.com|timestamp|Subject
    <added>\t<removed>\t<filename>    # one or more lines per commit
    <added>\t<removed>\t<filename>
    Author Name2|email2@domain.com|timestamp2|Subject2
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
            if len(parts) < 4:
                i += 1
                continue
            
            git_name = parts[0]
            email = parts[1]
            timestamp_str = parts[2]
            
            # Filter by user_email if specified
            if user_email and email != user_email:
                # Skip this commit entirely - move past all numstat lines
                i += 1
                while i < len(lines) and "|" not in lines[i]:
                    i += 1
                continue
            
            username = email.split("@")[0] if "@" in email else email
            timestamp = datetime.fromisoformat(timestamp_str.strip())
            
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
                "git_name": git_name,
                "username": username,
                "email": email,
                "rows_added": rows_added,
                "rows_removed": rows_removed,
                "timestamp": timestamp,
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
        ))
    
    # If we fetched num_commits + 1 commits, drop the oldest one (has empty spent_time)
    # This ensures we return exactly num_commits with valid spent_time data
    if len(commits) > num_commits:
        commits = commits[-num_commits:]
    
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
            "git_name": c.git_name,
            "username": c.username,
            "email": c.email,
            "rows_added": c.rows_added,
            "rows_removed": c.rows_removed,
            "spent_time": c.spent_time,
            "timestamp": c.timestamp.isoformat(),
            "error": c.error,
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
    num_commits: int,
    ssh_key_dir: Path,
) -> list[CommitStats]:
    """Process a single repository.
    
    Args:
        repo: Repository configuration.
        num_commits: Number of commits to fetch.
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
        success, error_msg = test_ssh_connection(host, ssh_key_dir)
    else:
        print(f"  HTTPS URL: {url}")
        success, error_msg = test_https_connection(url)
    
    print(f"  Branch: {repo.branch_name or 'default'}")

    if not success:
        print(f"  Connection test failed: {error_msg}")
        error_entry = CommitStats(
            git_name="",
            username="",
            email="",
            rows_added=0,
            rows_removed=0,
            spent_time="",
            timestamp=datetime.now(),
            error=error_msg,
        )
        return [error_entry]

    commits = fetch_git_log(
        url=url,
        num_commits=num_commits,
        branch=repo.branch_name,
        user_email=repo.user_email,
        ssh_key_dir=ssh_key_dir if is_ssh else None,
        is_ssh=is_ssh,
    )

    return commits


def process_all_repos(config: Config) -> dict[str, list[dict]]:
    """Process all repositories from config.
    
    Args:
        config: Configuration object.
    
    Returns:
        Dictionary mapping repo names to their commits.
    """
    ssh_key_dir = get_ssh_key_dir()
    results = {}
    
    for repo in config.repositories:
        try:
            commits = process_repository(
                repo=repo,
                num_commits=config.settings.num_commit,
                ssh_key_dir=ssh_key_dir,
            )
            # Convert to dict for JSON serialization
            results[repo.name] = [
                {
                    "git_name": c.git_name,
                    "username": c.username,
                    "email": c.email,
                    "rows_added": c.rows_added,
                    "rows_removed": c.rows_removed,
                    "spent_time": c.spent_time,
                    "timestamp": c.timestamp.isoformat(),
                    "error": "-",
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
        "--num-commits",
        type=int,
        default=10,
        help="Number of commits to fetch (default: 10)",
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
                print(f"  - {repo.name}: {repo.ssh_url}")
            print(f"Default num_commits: {config.settings.num_commit}")
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
        return process_all_repos(config)
    elif args.repo:
        # Find specific repo
        repo = next((r for r in config.repositories if r.name == args.repo), None)
        if repo is None:
            print(f"Error: Repository '{args.repo}' not found in config.", file=sys.stderr)
            sys.exit(1)
        
        ssh_key_dir = get_ssh_key_dir()
        commits = process_repository(
            repo=repo,
            num_commits=args.num_commits,
            ssh_key_dir=ssh_key_dir,
        )
        return {
            repo.name: [
                {
                    "git_name": c.git_name,
                    "username": c.username,
                    "email": c.email,
                    "rows_added": c.rows_added,
                    "rows_removed": c.rows_removed,
                    "spent_time": c.spent_time,
                    "timestamp": c.timestamp.isoformat(),
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
