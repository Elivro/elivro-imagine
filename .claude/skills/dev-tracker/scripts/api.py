"""
Dev Tracker API Client
"""

import json
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any

from config import API_URL, get_headers, REQUEST_TIMEOUT, validate_config
from git_utils import get_user_email


class DevTrackerError(Exception):
    """Dev Tracker API Error"""
    pass


def _make_request(
    method: str,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Make an API request"""
    if not validate_config():
        raise DevTrackerError("Invalid configuration")

    email = get_user_email()
    if not email:
        raise DevTrackerError("Could not determine git user email")

    url = f"{API_URL}/{endpoint}"
    headers = get_headers(email)

    req_data = None
    if data:
        req_data = json.dumps(data).encode('utf-8')

    request = urllib.request.Request(
        url,
        data=req_data,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        try:
            error_data = json.loads(error_body)
            raise DevTrackerError(error_data.get('error', str(e)))
        except json.JSONDecodeError:
            raise DevTrackerError(f"HTTP {e.code}: {error_body}")
    except urllib.error.URLError as e:
        raise DevTrackerError(f"Connection error: {e.reason}")


def create_task(
    title: str,
    description: Optional[str] = None,
    category: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    effort: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new task

    Args:
        title: Task title
        description: Optional task description
        category: Optional category ID
        status: Optional status (e.g. 'backlog'). If None, API defaults to 'in_progress'
        priority: Optional priority (low, medium, high, critical)
        effort: Optional effort (tiny, small, medium, large, massive)

    Returns:
        Created task object
    """
    data = {'title': title}
    if description:
        data['description'] = description
    if category:
        data['category'] = category
    if status:
        data['status'] = status
    if priority:
        data['priority'] = priority
    if effort:
        data['effort'] = effort

    result = _make_request('POST', 'tasks', data)
    return result.get('task', result)


def update_task(
    task_id: int,
    status: Optional[str] = None,
    summary: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[int] = None
) -> Dict[str, Any]:
    """
    Update a task

    Args:
        task_id: Task ID
        status: New status (backlog, in_progress, ready_for_release, testing, ready_for_production, deployed)
        summary: AI-generated summary
        title: New title
        description: New description
        category: New category ID

    Returns:
        Updated task object
    """
    data = {}
    if status:
        data['status'] = status
    if summary:
        data['summary'] = summary
    if title:
        data['title'] = title
    if description:
        data['description'] = description
    if category:
        data['category'] = category

    result = _make_request('PATCH', f'tasks/{task_id}', data)
    return result.get('task', result)


def delete_task(task_id: int) -> Dict[str, Any]:
    """
    Delete a task permanently

    Args:
        task_id: Task ID

    Returns:
        Response object with success status
    """
    return _make_request('DELETE', f'tasks/{task_id}')


def get_task(task_id: int) -> Dict[str, Any]:
    """
    Get a single task by ID

    Args:
        task_id: Task ID

    Returns:
        Task object
    """
    result = _make_request('GET', f'tasks/{task_id}')
    return result.get('task', result)


def get_my_tasks() -> List[Dict[str, Any]]:
    """
    Get all tasks assigned to the current user

    Returns:
        List of task objects
    """
    result = _make_request('GET', 'tasks?my_tasks=true')
    return result.get('tasks', [])


def get_all_active_tasks() -> List[Dict[str, Any]]:
    """
    Get all active tasks (for conflict detection)

    Returns:
        List of active task objects with assignee info
    """
    result = _make_request('GET', 'conflicts')
    return result.get('tasks', [])


def get_backlog_tasks() -> List[Dict[str, Any]]:
    """
    Get all tasks with backlog status

    Returns:
        List of backlog task objects
    """
    result = _make_request('GET', 'tasks?status=backlog')
    return result.get('tasks', [])


def log_milestone(
    task_id: int,
    milestone_type: str,
    message: str
) -> Dict[str, Any]:
    """
    Log a milestone for a task

    Args:
        task_id: Task ID
        milestone_type: Type (created, file_changed, committed, status_changed, conflict_acknowledged)
        message: Milestone message

    Returns:
        Created milestone object
    """
    data = {
        'type': milestone_type,
        'message': message,
    }

    result = _make_request('POST', f'tasks/{task_id}/milestones', data)
    return result.get('milestone', result)


def send_heartbeat(
    task_id: int,
    progress: Optional[int] = None,
    progress_note: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send a heartbeat for a task to signal active work and optionally update progress.

    This is a lightweight call that updates lastActivityAt and optionally progress.
    Should be called on every user prompt when a task is active.

    Args:
        task_id: Task ID
        progress: Optional progress percentage (0-99). 100 is reserved for merge.
        progress_note: Optional brief note about current progress state

    Returns:
        Response object with success status
    """
    data = {}
    if progress is not None:
        data['progress'] = min(99, max(0, progress))  # Cap at 99
    if progress_note is not None:
        data['progressNote'] = progress_note[:200]  # Limit length

    if data:
        return _make_request('POST', f'tasks/{task_id}/heartbeat', data)
    return _make_request('POST', f'tasks/{task_id}/heartbeat')


def get_milestones(task_id: int) -> List[Dict[str, Any]]:
    """
    Get milestones for a task

    Args:
        task_id: Task ID

    Returns:
        List of milestone objects
    """
    result = _make_request('GET', f'tasks/{task_id}/milestones')
    return result.get('milestones', [])


def get_categories() -> List[Dict[str, Any]]:
    """
    Get all categories

    Returns:
        List of category objects
    """
    result = _make_request('GET', 'categories')
    return result.get('categories', [])


def create_category(name: str, color: str = '#6366f1') -> Dict[str, Any]:
    """
    Create a new category

    Args:
        name: Category name
        color: Hex color code

    Returns:
        Created category object
    """
    data = {
        'name': name,
        'color': color,
    }

    result = _make_request('POST', 'categories', data)
    return result.get('category', result)


# ============================================================================
# Release Management
# ============================================================================

def get_releases(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get releases

    Args:
        status: Filter by status ('testing', 'deployed', or None for all)
        limit: Maximum number of releases to return

    Returns:
        List of release objects
    """
    params = f'?limit={limit}'
    if status:
        params += f'&status={status}'

    result = _make_request('GET', f'releases{params}')
    return result.get('releases', [])


def get_active_release() -> Optional[Dict[str, Any]]:
    """
    Get the currently active (testing) release

    Returns:
        Active release object or None if no active release
    """
    result = _make_request('GET', 'releases/active')
    return result.get('release')


def create_release(
    version: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    size: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new release and move ready_for_release tasks to testing

    Args:
        version: Semantic version (e.g., '1.2.0')
        title: Optional release title
        description: Optional release description
        size: Optional size ('tiny', 'small', 'medium', 'large', 'massive')

    Returns:
        Created release object with list of included tasks
    """
    data: Dict[str, Any] = {'version': version}
    if title:
        data['title'] = title
    if description:
        data['description'] = description
    if size:
        data['size'] = size

    return _make_request('POST', 'releases', data)


def complete_release(version: Optional[str] = None) -> Dict[str, Any]:
    """
    Complete a release: mark as deployed and update all tasks to deployed

    Args:
        version: Version to complete (optional - if not provided, completes active release)

    Returns:
        Completed release object with list of deployed tasks
    """
    data: Dict[str, Any] = {}
    if version:
        data['version'] = version

    return _make_request('POST', 'releases/complete', data)


def get_all_active_and_backlog_tasks() -> List[Dict[str, Any]]:
    """
    Get all tasks that are not deployed (for duplicate detection)

    Returns:
        List of task objects that are not in 'deployed' status
    """
    result = _make_request('GET', 'tasks')
    all_tasks = result.get('tasks', [])
    # Filter out deployed tasks - we want backlog, in_progress, ready_for_release, testing, ready_for_production
    return [t for t in all_tasks if t.get('status') != 'deployed']


def _normalize_title(title: str) -> str:
    """Normalize a title for comparison (lowercase, strip whitespace, remove punctuation)"""
    import re
    normalized = title.lower().strip()
    # Remove common punctuation and extra whitespace
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def _find_duplicate_task(title: str, existing_tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Find if a task with similar title already exists

    Args:
        title: Title to check
        existing_tasks: List of existing tasks to check against

    Returns:
        Matching task if found, None otherwise
    """
    normalized_new = _normalize_title(title)

    for task in existing_tasks:
        existing_title = task.get('title', '')
        normalized_existing = _normalize_title(existing_title)

        # Check for exact match after normalization
        if normalized_new == normalized_existing:
            return task

        # Check if one is a substring of the other (catches minor variations)
        if normalized_new in normalized_existing or normalized_existing in normalized_new:
            # Only match if they're at least 80% similar in length
            len_ratio = min(len(normalized_new), len(normalized_existing)) / max(len(normalized_new), len(normalized_existing))
            if len_ratio > 0.8:
                return task

    return None


def batch_import_tasks(file_path: str = 'backlog.json') -> Dict[str, Any]:
    """
    Import tasks from a JSON file in batch, skipping duplicates

    Args:
        file_path: Path to JSON file with tasks array

    Returns:
        Dict with 'created' (list of created tasks) and 'skipped' (list of skipped duplicates)

    JSON format:
    {
        "tasks": [
            {
                "title": "Task title",
                "description": "Optional description",
                "category": "Category Name",
                "priority": "low|medium|high|critical",
                "effort": "tiny|small|medium|large|massive"
            }
        ]
    }
    """
    import os

    # Resolve path relative to script directory if not absolute
    if not os.path.isabs(file_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tasks_data = data.get('tasks', [])
    if not tasks_data:
        raise DevTrackerError("No tasks found in JSON file")

    # Get existing non-deployed tasks for duplicate detection
    print("Checking for duplicates...")
    existing_tasks = get_all_active_and_backlog_tasks()
    print(f"Found {len(existing_tasks)} existing non-deployed tasks")

    # Get categories for name-to-id resolution
    categories = get_categories()
    category_map = {cat.get('name', '').lower(): cat.get('id') for cat in categories}

    created_tasks = []
    skipped_tasks = []

    for task_item in tasks_data:
        title = task_item.get('title')
        if not title:
            print(f"Skipping task with no title: {task_item}")
            continue

        # Check for duplicates
        duplicate = _find_duplicate_task(title, existing_tasks)
        if duplicate:
            skipped_tasks.append({
                'title': title,
                'existing_id': duplicate.get('id'),
                'existing_title': duplicate.get('title'),
                'existing_status': duplicate.get('status'),
            })
            print(f"Skipping duplicate: '{title}' (matches #{duplicate.get('id')}: '{duplicate.get('title')}')")
            continue

        # Resolve category name to ID
        category_id = None
        category_name = task_item.get('category')
        if category_name:
            category_id = category_map.get(category_name.lower())
            if not category_id:
                print(f"Warning: Category '{category_name}' not found, skipping category for task '{title}'")

        task = create_task(
            title=title,
            description=task_item.get('description'),
            category=category_id,
            status='backlog',
            priority=task_item.get('priority', 'medium'),
            effort=task_item.get('effort', 'medium')
        )
        created_tasks.append(task)
        # Add to existing tasks to prevent duplicates within the same batch
        existing_tasks.append(task)

    return {
        'created': created_tasks,
        'skipped': skipped_tasks,
    }


if __name__ == '__main__':
    import sys

    def print_usage():
        print("""Dev Tracker CLI

Usage: python api.py <command> [args]

Commands:
  tasks                          List my tasks
  active                         List all active tasks (conflict detection)
  backlog                        List backlog tasks
  create <title> [description]   Create a new task
  heartbeat <id> <progress> [note]  Send heartbeat for task
  update <id> <status> [summary] Update task status
  delete <id>                    Delete a task
  categories                     List categories
  batch [file]                   Import tasks from JSON file (default: backlog.json)
  test                           Test API connection
""")

    args = sys.argv[1:]
    if not args:
        print_usage()
        sys.exit(0)

    cmd = args[0]

    try:
        if cmd == 'tasks':
            tasks = get_my_tasks()
            if not tasks:
                print("No tasks assigned to you")
            for task in tasks:
                print(f"[{task.get('id')}] {task.get('title')} ({task.get('status')})")

        elif cmd == 'active':
            active = get_all_active_tasks()
            if not active:
                print("No active tasks")
            for task in active:
                assignee = task.get('assignee', {})
                email = assignee.get('email', 'unassigned') if assignee else 'unassigned'
                print(f"[{task.get('id')}] {task.get('title')} (by {email})")

        elif cmd == 'create':
            if len(args) < 2:
                print("Usage: python api.py create <title> [description] [--category <name>] [--priority <value>] [--effort <value>]")
                print("  --category: Dashboard, Candidates, Clients, Jobs, etc.")
                print("  --priority: low, medium, high, critical")
                print("  --effort: tiny, small, medium, large, massive")
                sys.exit(1)

            # Parse positional and optional arguments
            title = None
            description = None
            category_name = None
            priority = None
            effort = None

            i = 1
            positional_args = []
            while i < len(args):
                if args[i] == '--category' and i + 1 < len(args):
                    category_name = args[i + 1]
                    i += 2
                elif args[i] == '--priority' and i + 1 < len(args):
                    priority = args[i + 1]
                    i += 2
                elif args[i] == '--effort' and i + 1 < len(args):
                    effort = args[i + 1]
                    i += 2
                elif not args[i].startswith('--'):
                    positional_args.append(args[i])
                    i += 1
                else:
                    i += 1

            if not positional_args:
                print("Error: title is required")
                sys.exit(1)

            title = positional_args[0]
            description = positional_args[1] if len(positional_args) > 1 else None

            # Resolve category name to ID
            category_id = None
            if category_name:
                categories = get_categories()
                category_map = {cat.get('name', '').lower(): cat.get('id') for cat in categories}
                category_id = category_map.get(category_name.lower())
                if not category_id:
                    print(f"Warning: Category '{category_name}' not found")

            result = create_task(title, description, category=category_id, priority=priority, effort=effort)
            task = result
            print(f"Created task #{task.get('id')}: {task.get('title')}")
            if category_name:
                print(f"  Category: {category_name}")
            if priority:
                print(f"  Priority: {priority}")
            if effort:
                print(f"  Effort: {effort}")

        elif cmd == 'heartbeat':
            if len(args) < 3:
                print("Usage: python api.py heartbeat <task_id> <progress> [note]")
                sys.exit(1)
            task_id = int(args[1])
            progress = int(args[2])
            note = args[3] if len(args) > 3 else None
            send_heartbeat(task_id, progress, note)
            print(f"Heartbeat sent for task #{task_id} (progress: {progress}%)")

        elif cmd == 'update':
            if len(args) < 3:
                print("Usage: python api.py update <task_id> <status> [summary]")
                sys.exit(1)
            task_id = int(args[1])
            status = args[2]
            summary = args[3] if len(args) > 3 else None
            result = update_task(task_id, status=status, summary=summary)
            print(f"Updated task #{task_id} to {status}")

        elif cmd == 'delete':
            if len(args) < 2:
                print("Usage: python api.py delete <task_id>")
                sys.exit(1)
            task_id = int(args[1])
            delete_task(task_id)
            print(f"Deleted task #{task_id}")

        elif cmd == 'backlog':
            tasks = get_backlog_tasks()
            if not tasks:
                print("No backlog tasks")
            for task in tasks:
                priority = task.get('priority', 'medium')
                effort = task.get('effort', 'medium')
                print(f"[{task.get('id')}] {task.get('title')} (P:{priority} E:{effort})")

        elif cmd == 'categories':
            categories = get_categories()
            for cat in categories:
                print(f"  {cat.get('name')}")

        elif cmd == 'batch':
            file_path = args[1] if len(args) > 1 else 'backlog.json'
            print(f"Importing tasks from {file_path}...")
            result = batch_import_tasks(file_path)
            created = result.get('created', [])
            skipped = result.get('skipped', [])

            if created:
                task_ids = [f"#{t.get('id')}" for t in created]
                print(f"Created {len(created)} backlog tasks ({', '.join(task_ids)})")
            else:
                print("No new tasks created")

            if skipped:
                print(f"Skipped {len(skipped)} duplicates:")
                for s in skipped:
                    print(f"  - '{s['title']}' (matches #{s['existing_id']}: '{s['existing_title']}' [{s['existing_status']}])")

        elif cmd == 'test':
            print("Testing Dev Tracker API...")
            tasks = get_my_tasks()
            print(f"Connection OK. You have {len(tasks)} task(s).")

        else:
            print(f"Unknown command: {cmd}")
            print_usage()
            sys.exit(1)

    except DevTrackerError as e:
        print(f"Error: {e}")
        sys.exit(1)
