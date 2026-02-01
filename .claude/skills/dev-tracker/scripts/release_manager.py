"""
Release Manager - Git and API operations for release management
"""

import subprocess
import sys
import re
from typing import Optional, Tuple, List, Dict, Any

from api import (
    create_release as api_create_release,
    complete_release as api_complete_release,
    get_releases,
    get_active_release,
    update_task,
    log_milestone,
    get_my_tasks,
    DevTrackerError,
)
from git_utils import get_current_branch, get_user_email


class ReleaseError(Exception):
    """Release operation error"""
    pass


def run_git(args: List[str], check: bool = True) -> Tuple[int, str, str]:
    """
    Run a git command and return (returncode, stdout, stderr)
    """
    try:
        result = subprocess.run(
            ['git'] + args,
            capture_output=True,
            text=True,
            timeout=60
        )
        if check and result.returncode != 0:
            raise ReleaseError(f"Git command failed: git {' '.join(args)}\n{result.stderr}")
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        raise ReleaseError(f"Git command timed out: git {' '.join(args)}")


def validate_semver(version: str) -> bool:
    """Validate semantic version format"""
    pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$'
    return bool(re.match(pattern, version))


def get_uncommitted_changes() -> List[str]:
    """Get list of uncommitted changes"""
    _, stdout, _ = run_git(['status', '--porcelain'])
    if not stdout:
        return []
    return [line for line in stdout.split('\n') if line.strip()]


def is_feature_branch(branch: str) -> bool:
    """Check if branch is a feature branch"""
    prefixes = ('feature/', 'fix/', 'hotfix/', 'bugfix/')
    return branch.startswith(prefixes)


def branch_exists(branch: str, remote: bool = False) -> bool:
    """Check if a branch exists"""
    if remote:
        code, _, _ = run_git(['show-ref', '--verify', '--quiet', f'refs/remotes/origin/{branch}'], check=False)
    else:
        code, _, _ = run_git(['show-ref', '--verify', '--quiet', f'refs/heads/{branch}'], check=False)
    return code == 0


def fetch_origin() -> None:
    """Fetch latest from origin"""
    run_git(['fetch', 'origin'])


def create_release(
    version: str,
    title: Optional[str] = None,
    auto_commit: bool = True,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Create a release branch and register it in Dev Tracker.

    Args:
        version: Semantic version (e.g., '1.2.0')
        title: Optional release title
        auto_commit: Whether to auto-commit uncommitted changes
        dry_run: If True, only show what would happen

    Returns:
        Dict with release info and tasks
    """
    result = {
        'success': False,
        'version': version,
        'branch': f'release/{version}',
        'actions': [],
        'tasks': [],
        'errors': [],
    }

    # Validate version
    if not validate_semver(version):
        result['errors'].append(f"Invalid version format: {version}. Use semantic versioning (e.g., 1.2.0)")
        return result

    result['actions'].append(f"Validated version: {version}")

    # Check for uncommitted changes
    changes = get_uncommitted_changes()
    if changes:
        if auto_commit:
            result['actions'].append(f"Found {len(changes)} uncommitted changes - will commit first")
        else:
            result['errors'].append(f"Uncommitted changes detected. Commit or stash them first.")
            result['uncommitted'] = changes
            return result

    # Fetch origin
    if not dry_run:
        fetch_origin()
    result['actions'].append("Fetched origin")

    # Check if release branch already exists
    release_branch = f'release/{version}'
    if branch_exists(release_branch) or branch_exists(release_branch, remote=True):
        result['errors'].append(f"Release branch {release_branch} already exists")
        return result

    # Check if develop exists
    if not branch_exists('develop', remote=True):
        result['errors'].append("Remote branch origin/develop does not exist")
        return result

    result['actions'].append("Verified origin/develop exists")

    if dry_run:
        result['actions'].append(f"[DRY RUN] Would create branch: {release_branch} from origin/develop")
        result['actions'].append(f"[DRY RUN] Would call API to create release")
        result['success'] = True
        return result

    # Create release branch from origin/develop
    try:
        run_git(['checkout', '-b', release_branch, 'origin/develop'])
        result['actions'].append(f"Created branch: {release_branch}")
    except ReleaseError as e:
        result['errors'].append(str(e))
        return result

    # Push to origin
    try:
        run_git(['push', '-u', 'origin', release_branch])
        result['actions'].append(f"Pushed {release_branch} to origin")
    except ReleaseError as e:
        result['errors'].append(f"Failed to push: {e}")
        # Try to cleanup
        run_git(['checkout', 'develop'], check=False)
        run_git(['branch', '-D', release_branch], check=False)
        return result

    # Call API to create release
    try:
        api_result = api_create_release(version=version, title=title)
        result['release'] = api_result.get('release', {})
        result['tasks'] = api_result.get('tasks', [])
        result['actions'].append(f"Created release in Dev Tracker: {len(result['tasks'])} tasks included")
        result['success'] = True
    except DevTrackerError as e:
        result['errors'].append(f"API error: {e}")
        result['actions'].append("Release branch created but API call failed")
        # Branch exists but API failed - partial success
        result['partial'] = True

    return result


def complete_release(
    version: Optional[str] = None,
    merge_to_main: bool = False,
    delete_branch: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Complete a release: mark as deployed and optionally merge branches.

    Args:
        version: Version to complete (None = active release)
        merge_to_main: Whether to merge to main branch
        delete_branch: Whether to delete the release branch
        dry_run: If True, only show what would happen

    Returns:
        Dict with completion info
    """
    result = {
        'success': False,
        'version': version,
        'actions': [],
        'tasks': [],
        'errors': [],
    }

    # Get release info
    if version:
        releases = get_releases(status='testing')
        release = next((r for r in releases if r['version'] == version), None)
        if not release:
            result['errors'].append(f"Release {version} not found or not in testing status")
            return result
    else:
        release = get_active_release()
        if not release:
            result['errors'].append("No active release found in testing status")
            return result
        version = release['version']

    result['version'] = version
    result['release'] = release
    result['actions'].append(f"Found release: {version}")

    release_branch = f'release/{version}'

    if dry_run:
        result['actions'].append(f"[DRY RUN] Would mark release {version} as deployed")
        if merge_to_main:
            result['actions'].append(f"[DRY RUN] Would merge {release_branch} to main")
        if delete_branch:
            result['actions'].append(f"[DRY RUN] Would delete {release_branch}")
        result['success'] = True
        return result

    # Call API to complete release
    try:
        api_result = api_complete_release(version=version)
        result['tasks'] = api_result.get('tasks', [])
        result['deployed_at'] = api_result.get('release', {}).get('deployedAt')
        result['actions'].append(f"Marked release as deployed: {len(result['tasks'])} tasks completed")
    except DevTrackerError as e:
        result['errors'].append(f"API error: {e}")
        return result

    # Optional: Merge to main
    if merge_to_main:
        try:
            fetch_origin()
            current_branch = get_current_branch()

            # Merge to main
            run_git(['checkout', 'main'])
            run_git(['pull', 'origin', 'main'])
            run_git(['merge', '--no-ff', release_branch, '-m', f'Merge release {version}'])
            run_git(['push', 'origin', 'main'])
            result['actions'].append(f"Merged {release_branch} to main")

            # Tag the release
            run_git(['tag', '-a', f'v{version}', '-m', f'Release {version}'])
            run_git(['push', 'origin', f'v{version}'])
            result['actions'].append(f"Created tag: v{version}")

            # Merge back to develop
            run_git(['checkout', 'develop'])
            run_git(['pull', 'origin', 'develop'])
            run_git(['merge', '--no-ff', release_branch, '-m', f'Merge release {version} back to develop'])
            run_git(['push', 'origin', 'develop'])
            result['actions'].append(f"Merged {release_branch} back to develop")

            # Return to original branch
            run_git(['checkout', current_branch], check=False)

        except ReleaseError as e:
            result['errors'].append(f"Git merge error: {e}")
            result['actions'].append("Release completed in tracker but git merge failed")

    # Optional: Delete branch
    if delete_branch and not result['errors']:
        try:
            run_git(['branch', '-d', release_branch], check=False)
            run_git(['push', 'origin', '--delete', release_branch], check=False)
            result['actions'].append(f"Deleted branch: {release_branch}")
        except ReleaseError:
            result['actions'].append(f"Could not delete branch: {release_branch}")

    result['success'] = True
    return result


def mark_task_ready(
    task_id: Optional[int] = None,
    commit_message: Optional[str] = None,
    merge_to_develop: bool = True,
    delete_feature_branch: bool = False,
    summary: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Mark a task as ready for release.

    Steps:
    1. Commit any uncommitted changes
    2. If on feature branch, merge to develop
    3. Update task status to ready_for_release

    Args:
        task_id: Task ID (None = get from active tasks)
        commit_message: Custom commit message
        merge_to_develop: Whether to merge feature branch to develop
        delete_feature_branch: Whether to delete the feature branch after merge
        summary: Optional task summary
        dry_run: If True, only show what would happen

    Returns:
        Dict with operation info
    """
    result = {
        'success': False,
        'task_id': task_id,
        'actions': [],
        'errors': [],
    }

    # Get current branch
    current_branch = get_current_branch()
    result['branch'] = current_branch
    result['is_feature_branch'] = is_feature_branch(current_branch)

    # Find task if not specified
    if not task_id:
        try:
            tasks = get_my_tasks()
            active_tasks = [t for t in tasks if t.get('status') == 'in_progress']
            if not active_tasks:
                result['errors'].append("No active task found. Start a task with /dev-tracker first.")
                return result
            task_id = active_tasks[0]['id']
            result['task'] = active_tasks[0]
        except DevTrackerError as e:
            result['errors'].append(f"Could not fetch tasks: {e}")
            return result

    result['task_id'] = task_id
    result['actions'].append(f"Found active task: {task_id}")

    # Check for uncommitted changes
    changes = get_uncommitted_changes()
    if changes:
        result['uncommitted_changes'] = changes
        result['actions'].append(f"Found {len(changes)} uncommitted changes")

        if dry_run:
            result['actions'].append(f"[DRY RUN] Would commit {len(changes)} changes")
        else:
            # Auto-generate commit message if not provided
            if not commit_message:
                task_title = result.get('task', {}).get('title', f'Task {task_id}')
                commit_message = f"Complete {task_title}"

            try:
                run_git(['add', '-A'])
                run_git(['commit', '-m', commit_message])
                result['actions'].append(f"Committed changes: {commit_message}")
            except ReleaseError as e:
                result['errors'].append(f"Commit failed: {e}")
                return result
    else:
        result['actions'].append("No uncommitted changes")

    # Handle feature branch merge
    if result['is_feature_branch'] and merge_to_develop:
        if dry_run:
            result['actions'].append(f"[DRY RUN] Would merge {current_branch} to develop")
        else:
            try:
                fetch_origin()

                # Push current branch first
                run_git(['push', '-u', 'origin', current_branch], check=False)
                result['actions'].append(f"Pushed {current_branch} to origin")

                # Switch to develop
                if not branch_exists('develop'):
                    run_git(['checkout', '-b', 'develop', 'origin/develop'])
                else:
                    run_git(['checkout', 'develop'])
                    run_git(['pull', 'origin', 'develop'])

                # Merge feature branch
                run_git(['merge', '--no-ff', current_branch, '-m', f'Merge {current_branch} into develop'])
                result['actions'].append(f"Merged {current_branch} into develop")

                # Push develop
                run_git(['push', 'origin', 'develop'])
                result['actions'].append("Pushed develop to origin")

                # Delete feature branch if requested
                if delete_feature_branch:
                    run_git(['branch', '-d', current_branch], check=False)
                    run_git(['push', 'origin', '--delete', current_branch], check=False)
                    result['actions'].append(f"Deleted feature branch: {current_branch}")
                    result['branch_deleted'] = True
                else:
                    # Stay on develop
                    result['current_branch'] = 'develop'

            except ReleaseError as e:
                result['errors'].append(f"Merge failed: {e}")
                # Try to return to original branch
                run_git(['checkout', current_branch], check=False)
                return result
    elif not result['is_feature_branch']:
        # On develop or other branch - just push
        if not dry_run and changes:
            try:
                run_git(['push', 'origin', current_branch])
                result['actions'].append(f"Pushed to origin/{current_branch}")
            except ReleaseError as e:
                result['errors'].append(f"Push failed: {e}")
                return result

    # Update task status in Dev Tracker
    if dry_run:
        result['actions'].append(f"[DRY RUN] Would update task {task_id} to ready_for_release")
        result['success'] = True
        return result

    try:
        update_data = {'status': 'ready_for_release'}
        if summary:
            update_data['summary'] = summary

        update_task(task_id, status='ready_for_release', summary=summary)
        result['actions'].append(f"Updated task {task_id} to ready_for_release")

        log_milestone(task_id, 'status_changed', 'Marked as ready for release')
        result['actions'].append("Logged milestone")

        result['success'] = True
    except DevTrackerError as e:
        result['errors'].append(f"API error: {e}")
        result['actions'].append("Git operations completed but task update failed")
        result['partial'] = True

    return result


def print_result(result: Dict[str, Any], operation: str) -> None:
    """Print operation result in a formatted way"""
    print(f"\n{'=' * 50}")
    print(f"{operation.upper()}")
    print('=' * 50)

    if result.get('success'):
        print("✓ SUCCESS")
    elif result.get('partial'):
        print("⚠ PARTIAL SUCCESS")
    else:
        print("✗ FAILED")

    print(f"\nVersion: {result.get('version', 'N/A')}")

    if result.get('actions'):
        print("\nActions:")
        for action in result['actions']:
            print(f"  • {action}")

    if result.get('tasks'):
        print(f"\nTasks ({len(result['tasks'])}):")
        for task in result['tasks']:
            print(f"  • [{task.get('id')}] {task.get('title')}")

    if result.get('errors'):
        print("\nErrors:")
        for error in result['errors']:
            print(f"  ✗ {error}")

    print()


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Release Manager')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # create-release command
    create_parser = subparsers.add_parser('create', help='Create a new release')
    create_parser.add_argument('version', help='Semantic version (e.g., 1.2.0)')
    create_parser.add_argument('--title', help='Release title')
    create_parser.add_argument('--dry-run', action='store_true', help='Show what would happen')

    # complete-release command
    complete_parser = subparsers.add_parser('complete', help='Complete a release')
    complete_parser.add_argument('version', nargs='?', help='Version to complete (default: active release)')
    complete_parser.add_argument('--merge', action='store_true', help='Merge to main and develop')
    complete_parser.add_argument('--delete-branch', action='store_true', help='Delete release branch')
    complete_parser.add_argument('--dry-run', action='store_true', help='Show what would happen')

    # mark-ready command
    ready_parser = subparsers.add_parser('mark-ready', help='Mark task as ready for release')
    ready_parser.add_argument('--task-id', type=int, help='Task ID (default: active task)')
    ready_parser.add_argument('--message', '-m', help='Commit message')
    ready_parser.add_argument('--summary', help='Task summary')
    ready_parser.add_argument('--no-merge', action='store_true', help='Skip merge to develop')
    ready_parser.add_argument('--delete-branch', action='store_true', help='Delete feature branch after merge')
    ready_parser.add_argument('--dry-run', action='store_true', help='Show what would happen')

    # status command
    status_parser = subparsers.add_parser('status', help='Show release status')

    args = parser.parse_args()

    if args.command == 'create':
        result = create_release(
            version=args.version,
            title=args.title,
            dry_run=args.dry_run
        )
        print_result(result, 'Create Release')

    elif args.command == 'complete':
        result = complete_release(
            version=args.version,
            merge_to_main=args.merge,
            delete_branch=args.delete_branch,
            dry_run=args.dry_run
        )
        print_result(result, 'Complete Release')

    elif args.command == 'mark-ready':
        result = mark_task_ready(
            task_id=args.task_id,
            commit_message=args.message,
            merge_to_develop=not args.no_merge,
            delete_feature_branch=args.delete_branch,
            summary=args.summary,
            dry_run=args.dry_run
        )
        print_result(result, 'Mark Ready')

    elif args.command == 'status':
        print("\n=== RELEASE STATUS ===\n")

        active = get_active_release()
        if active:
            print(f"Active Release: {active['version']}")
            print(f"  Status: {active['status']}")
        else:
            print("No active release in testing")

        print("\nRecent Releases:")
        releases = get_releases(limit=5)
        for r in releases:
            status_icon = "🚀" if r['status'] == 'deployed' else "🧪"
            print(f"  {status_icon} {r['version']} ({r['status']}) - {r.get('taskCount', 0)} tasks")

    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
