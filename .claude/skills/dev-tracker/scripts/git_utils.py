"""
Git Utilities for Dev Tracker
"""

import os
import subprocess
from typing import Optional, List, Dict


def run_git_command(args: List[str]) -> Optional[str]:
    """Run a git command and return output"""
    try:
        result = subprocess.run(
            ['git'] + args,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_user_email() -> Optional[str]:
    """Get the developer email from env var or git config"""
    # Prefer explicit env var over git config
    env_email = os.environ.get('DEV_TRACKER_EMAIL')
    if env_email:
        return env_email
    return run_git_command(['config', 'user.email'])


def get_user_name() -> Optional[str]:
    """Get the configured git user name"""
    return run_git_command(['config', 'user.name'])


def get_current_branch() -> Optional[str]:
    """Get the current git branch name"""
    return run_git_command(['branch', '--show-current'])


def get_recent_commits(count: int = 5) -> List[Dict[str, str]]:
    """Get recent commits with hash, message, and author"""
    output = run_git_command([
        'log',
        f'-{count}',
        '--pretty=format:%H|%s|%ae|%ar'
    ])

    if not output:
        return []

    commits = []
    for line in output.split('\n'):
        parts = line.split('|', 3)
        if len(parts) == 4:
            commits.append({
                'hash': parts[0],
                'message': parts[1],
                'author_email': parts[2],
                'relative_time': parts[3],
            })

    return commits


def get_changed_files() -> List[str]:
    """Get list of currently changed files (staged and unstaged)"""
    output = run_git_command(['status', '--porcelain'])

    if not output:
        return []

    files = []
    for line in output.split('\n'):
        if line:
            # Format is: XY filename
            # Skip the status characters
            filename = line[3:].strip()
            files.append(filename)

    return files


def get_staged_files() -> List[str]:
    """Get list of staged files"""
    output = run_git_command(['diff', '--cached', '--name-only'])

    if not output:
        return []

    return output.split('\n')


def get_repo_root() -> Optional[str]:
    """Get the root directory of the git repository"""
    return run_git_command(['rev-parse', '--show-toplevel'])


def get_remote_url() -> Optional[str]:
    """Get the remote origin URL"""
    return run_git_command(['remote', 'get-url', 'origin'])


if __name__ == '__main__':
    # Test the utilities
    print(f"Email: {get_user_email()}")
    print(f"Name: {get_user_name()}")
    print(f"Branch: {get_current_branch()}")
    print(f"Changed files: {get_changed_files()}")
    print(f"Recent commits: {get_recent_commits(3)}")
