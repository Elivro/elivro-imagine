#!/usr/bin/env python3
"""
Extract commits between versions for changelog generation.

Usage:
    python get_commits.py                     # Auto-detect release branch, compare to previous tag
    python get_commits.py <version>           # Compare against previous minor/major
    python get_commits.py <from> <to>         # Compare between two refs

Examples:
    python get_commits.py                     # On release/v0.6.0, compares v0.5.0..release/v0.6.0
    python get_commits.py v0.5.0              # Auto-finds previous minor/major (e.g., v0.4.0)
    python get_commits.py v0.4.0 v0.5.0       # Explicit range
"""

import subprocess
import sys
import re
from dataclasses import dataclass
from typing import Optional


# Paths to exclude from changelog (internal/admin stuff not visible to end users)
EXCLUDED_PATHS = [
    # Admin/system UI (not for regular users)
    "src/app/(payload)/",
    "src/app/(system-admin)/",
    "src/app/admin/",
    "src/app/api/",
    "src/app/monitoring/",
    # Backend/database internals
    "src/collections/",
    "src/migrations/",
    "src/hooks/",
    "src/access/",
    "src/jobs/",
    # Development/CI files
    "scripts/",
    ".github/",
    ".claude/",
    "docs/",
    "tests/",
    "__tests__/",
    ".env",
    "payload.config.ts",
    "payload-types.ts",
    # Config files
    "eslint",
    "tsconfig",
    "next.config",
    "tailwind.config",
    "postcss.config",
]

# Commit prefixes that are internal (not user-facing)
INTERNAL_PREFIXES = [
    "Refactor",
    "Reformat",
    "Document",
    "Docs",
    "Make",
    "Bump",
    "Merge",
    "Revert",
    "WIP",
    "chore",
    "ci",
    "test",
]


@dataclass
class Commit:
    hash: str
    author: str
    date: str
    subject: str
    body: str
    files: list[str]
    is_internal: bool = False


def run_git(args: list[str]) -> str:
    """Run a git command and return output."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git command failed: {result.stderr}")
    return result.stdout.strip()


def get_tags() -> list[str]:
    """Get all version tags sorted by version number."""
    output = run_git(["tag", "--list", "v*", "--sort=-version:refname"])
    return [t for t in output.split("\n") if t]


def parse_version(tag: str) -> Optional[tuple[int, int, int]]:
    """Parse a version tag like v1.2.3 into (major, minor, patch)."""
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def get_current_branch() -> Optional[str]:
    """Get the current git branch name."""
    try:
        return run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    except RuntimeError:
        return None


def parse_release_branch(branch: str) -> Optional[str]:
    """Extract version from release branch name like 'release/v0.6.0'."""
    match = re.match(r"release/v?(\d+\.\d+\.\d+)", branch)
    if match:
        return f"v{match.group(1)}"
    return None


def find_latest_tag() -> Optional[str]:
    """Find the most recent version tag."""
    tags = get_tags()
    if tags:
        return tags[0]
    return None


def find_previous_tag_for_release(release_version: str) -> Optional[str]:
    """Find the previous tag for a release branch version.

    For release/v0.6.0, finds v0.5.0 (previous minor/major).
    """
    return find_previous_minor_or_major(release_version)


def find_previous_minor_or_major(target_tag: str) -> Optional[str]:
    """Find the previous tag that is a minor or major version change (skip patches)."""
    target_version = parse_version(target_tag)
    if not target_version:
        return None

    target_major, target_minor, _ = target_version
    tags = get_tags()

    for tag in tags:
        version = parse_version(tag)
        if not version:
            continue

        major, minor, patch = version

        # Skip if same or newer version
        if (major, minor) >= (target_major, target_minor):
            continue

        # Skip patch versions (e.g., v0.4.1, v0.4.2) - only want x.y.0
        if patch != 0:
            continue

        # Found a previous minor/major version (patch == 0)
        return tag

    return None


def is_internal_commit(subject: str, files: list[str]) -> bool:
    """Check if a commit is internal (not user-facing)."""
    # Check subject prefix
    subject_lower = subject.lower()
    for prefix in INTERNAL_PREFIXES:
        if subject_lower.startswith(prefix.lower()):
            return True

    # Check if all changed files are in excluded paths
    if files:
        all_internal = all(
            any(f.startswith(excluded) or excluded in f for excluded in EXCLUDED_PATHS)
            for f in files
        )
        if all_internal:
            return True

    return False


def get_commits(from_ref: str, to_ref: str) -> list[Commit]:
    """Get all commits between two refs."""
    # Get commit hashes
    log_output = run_git([
        "log",
        f"{from_ref}..{to_ref}",
        "--format=%H",
        "--no-merges",
    ])

    if not log_output:
        return []

    commits = []
    for commit_hash in log_output.split("\n"):
        if not commit_hash:
            continue

        # Get commit details
        details = run_git([
            "log",
            "-1",
            commit_hash,
            "--format=%h%n%an%n%ci%n%s%n%b",
        ])
        lines = details.split("\n")

        short_hash = lines[0]
        author = lines[1]
        date = lines[2].split()[0]  # Just the date part
        subject = lines[3]
        body = "\n".join(lines[4:]).strip()

        # Get changed files
        files_output = run_git([
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit_hash,
        ])
        files = [f for f in files_output.split("\n") if f]

        is_internal = is_internal_commit(subject, files)

        commits.append(Commit(
            hash=short_hash,
            author=author,
            date=date,
            subject=subject,
            body=body,
            files=files,
            is_internal=is_internal,
        ))

    return commits


def categorize_commits(commits: list[Commit]) -> dict[str, list[Commit]]:
    """Categorize commits by type."""
    categories = {
        "features": [],
        "fixes": [],
        "improvements": [],
        "other": [],
        "internal": [],
    }

    for commit in commits:
        if commit.is_internal:
            categories["internal"].append(commit)
            continue

        subject_lower = commit.subject.lower()

        if subject_lower.startswith("add") or subject_lower.startswith("feat"):
            categories["features"].append(commit)
        elif subject_lower.startswith("fix"):
            categories["fixes"].append(commit)
        elif any(subject_lower.startswith(p) for p in ["improve", "enhance", "update", "optimize"]):
            categories["improvements"].append(commit)
        else:
            categories["other"].append(commit)

    return categories


def print_commits(from_ref: str, to_ref: str, commits: list[Commit], categories: dict):
    """Print commits in a structured format."""
    from_date = run_git(["log", "-1", "--format=%ci", from_ref]).split()[0]
    to_date = run_git(["log", "-1", "--format=%ci", to_ref]).split()[0]

    print("=" * 70)
    print(f"CHANGELOG COMMITS: {from_ref} ({from_date}) -> {to_ref} ({to_date})")
    print("=" * 70)
    print()

    user_facing = len(commits) - len(categories["internal"])
    print(f"Total commits: {len(commits)}")
    print(f"User-facing commits: {user_facing}")
    print(f"Internal commits (excluded): {len(categories['internal'])}")
    print()

    print("=" * 70)
    print("USER-FACING CHANGES (for changelog)")
    print("=" * 70)

    if categories["features"]:
        print("\n### [NEW] Features")
        for c in categories["features"]:
            print(f"  {c.hash} {c.subject}")
            if c.body:
                for line in c.body.split("\n")[:3]:
                    if line.strip():
                        print(f"         {line.strip()}")

    if categories["fixes"]:
        print("\n### [FIX] Bug Fixes")
        for c in categories["fixes"]:
            print(f"  {c.hash} {c.subject}")

    if categories["improvements"]:
        print("\n### [IMP] Improvements")
        for c in categories["improvements"]:
            print(f"  {c.hash} {c.subject}")

    if categories["other"]:
        print("\n### [OTHER] Other Changes")
        for c in categories["other"]:
            print(f"  {c.hash} {c.subject}")

    print()
    print("=" * 70)
    print("INTERNAL CHANGES (excluded from changelog)")
    print("=" * 70)
    if categories["internal"]:
        for c in categories["internal"]:
            reason = "internal prefix" if any(
                c.subject.lower().startswith(p.lower()) for p in INTERNAL_PREFIXES
            ) else "internal files only"
            print(f"  {c.hash} {c.subject} [{reason}]")
    else:
        print("  (none)")

    print()
    print("=" * 70)
    print("FILES CHANGED (user-facing commits only)")
    print("=" * 70)

    all_files = set()
    for cat_name, cat_commits in categories.items():
        if cat_name == "internal":
            continue
        for c in cat_commits:
            all_files.update(c.files)

    # Group by directory
    dirs: dict[str, int] = {}
    for f in all_files:
        if "/" in f:
            dir_name = f.rsplit("/", 1)[0]
        else:
            dir_name = "."
        dirs[dir_name] = dirs.get(dir_name, 0) + 1

    for dir_name, count in sorted(dirs.items(), key=lambda x: -x[1])[:15]:
        print(f"  {count:3d} {dir_name}/")

    print()
    print("=" * 70)
    print("END OF CHANGELOG DATA")
    print("=" * 70)


def main():
    if len(sys.argv) < 2:
        # No arguments: auto-detect release branch
        current_branch = get_current_branch()
        if not current_branch:
            print("Error: Could not determine current branch")
            sys.exit(1)

        release_version = parse_release_branch(current_branch)
        if release_version:
            # On a release branch - compare against previous tag
            to_ref = current_branch
            from_ref = find_previous_tag_for_release(release_version)

            if not from_ref:
                # Fall back to latest tag if no previous minor/major found
                from_ref = find_latest_tag()

            if not from_ref:
                print(f"Error: Could not find a previous tag to compare against")
                print("\nAvailable tags:")
                for tag in get_tags()[:10]:
                    print(f"  {tag}")
                sys.exit(1)

            print(f"Detected release branch: {current_branch}")
            print(f"Target version: {release_version}")
            print(f"Comparing against: {from_ref}")
            print()
        else:
            # Not on a release branch - show help
            print(__doc__)
            print(f"\nCurrent branch: {current_branch}")
            print("(Not a release branch - provide a version argument)")
            print("\nAvailable tags:")
            for tag in get_tags()[:10]:
                print(f"  {tag}")
            sys.exit(1)

    elif len(sys.argv) == 2:
        # Single argument: find previous minor/major automatically
        to_ref = sys.argv[1]
        from_ref = find_previous_minor_or_major(to_ref)

        if not from_ref:
            print(f"Error: Could not find a previous minor/major version for {to_ref}")
            print("\nAvailable tags:")
            for tag in get_tags()[:10]:
                print(f"  {tag}")
            sys.exit(1)

        print(f"Auto-detected previous version: {from_ref}")
        print()
    else:
        from_ref = sys.argv[1]
        to_ref = sys.argv[2]

    # Validate refs
    try:
        run_git(["rev-parse", "--verify", from_ref])
        run_git(["rev-parse", "--verify", to_ref])
    except RuntimeError as e:
        print(f"Error: Invalid git reference - {e}")
        sys.exit(1)

    commits = get_commits(from_ref, to_ref)
    categories = categorize_commits(commits)
    print_commits(from_ref, to_ref, commits, categories)


if __name__ == "__main__":
    main()
