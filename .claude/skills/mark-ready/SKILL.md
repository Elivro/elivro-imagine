---
name: Mark Ready
description: Commit changes, merge feature branch to develop, and mark task as ready for release in Dev Tracker
when_to_use: when finishing a task, completing a feature, done with implementation, ready to merge to develop, or preparing work for the next release
version: 1.0.0
---

# Mark Ready

Commits any pending changes, merges feature branch to develop (if applicable), and marks the active task as "Ready for Release" in Dev Tracker.

## Usage

```
/mark-ready
```

## Execution

Run the Python script from repo root:

```bash
cd .claude/skills/dev-tracker/scripts && python release_manager.py mark-ready
```

**Options:**
```bash
# With custom commit message
python release_manager.py mark-ready -m "Complete user authentication feature"

# With task summary (for release notes)
python release_manager.py mark-ready --summary "Added OAuth2 login flow with Google and GitHub providers"

# Skip merge to develop (just update task status)
python release_manager.py mark-ready --no-merge

# Delete feature branch after merge
python release_manager.py mark-ready --delete-branch

# Specify task ID (if not using active task)
python release_manager.py mark-ready --task-id 42

# Preview without making changes
python release_manager.py mark-ready --dry-run
```

## What It Does

1. Finds active task (or uses specified task ID)
2. Commits any uncommitted changes (auto-generates message if not provided)
3. If on feature branch (`feature/*`, `fix/*`, `hotfix/*`, `bugfix/*`):
   - Pushes feature branch to origin
   - Switches to develop
   - Merges feature branch with `--no-ff`
   - Pushes develop to origin
   - Optionally deletes feature branch
4. If on develop/other branch:
   - Just commits and pushes
5. Updates task status to "ready_for_release" in Dev Tracker
6. Logs status change milestone

## When to Suggest This Skill

Suggest `/mark-ready` when the user:
- Says "I'm done with this feature" or "task is complete"
- Mentions "ready to merge" or "ready for review"
- Wants to "finish this task" or "wrap this up"
- Says "this is ready for the next release"
- Completes implementation and tests pass
- Asks about "marking task as done"

## Output

```
==================================================
MARK READY
==================================================
✓ SUCCESS

Actions:
  • Found active task: 42
  • Found 3 uncommitted changes
  • Committed changes: Complete user authentication feature
  • Pushed feature/user-auth to origin
  • Merged feature/user-auth into develop
  • Pushed develop to origin
  • Updated task 42 to ready_for_release
  • Logged milestone
```

## Feature Branch Detection

Automatically detects feature branches by prefix:
- `feature/*` - New features
- `fix/*` - Bug fixes
- `hotfix/*` - Urgent fixes
- `bugfix/*` - Bug fixes (alternative)

Non-feature branches (like `develop` or `main`) skip the merge step and just commit/push directly.

## Prerequisites

- Active task in Dev Tracker (status: `in_progress`)
- Dev Tracker API configured
- Git repository with proper remote setup
