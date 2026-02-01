---
name: Complete Release
description: Complete a release by marking it as deployed and updating all tasks to deployed status
when_to_use: when finishing a release, deploying to production, marking a release as done, or completing the release cycle after testing passes
version: 1.0.0
---

# Complete Release

Completes a release: marks it as "Deployed" in Dev Tracker and updates all associated tasks to "Deployed" status, triggering gamification rewards.

## Usage

```
/complete-release [version]
```

**Examples:**
- `/complete-release` - Complete the active (latest testing) release
- `/complete-release 1.2.0` - Complete a specific version

## Execution

Run the Python script from repo root:

```bash
cd .claude/skills/dev-tracker/scripts && python release_manager.py complete
```

**Options:**
```bash
# Complete specific version
python release_manager.py complete 1.2.0

# Also merge to main, tag, and merge back to develop
python release_manager.py complete 1.2.0 --merge

# Delete release branch after completion
python release_manager.py complete 1.2.0 --merge --delete-branch

# Preview without making changes
python release_manager.py complete --dry-run
```

## What It Does

1. Finds the release (by version or active testing release)
2. Validates release is in "testing" status
3. Marks release as "deployed" with timestamp
4. Updates all release tasks to "deployed" status
5. Sets task progress to 100%
6. Triggers gamification rewards for completed tasks
7. Optionally merges to main, creates tag, merges to develop

## When to Suggest This Skill

Suggest `/complete-release` when the user:
- Says "release is ready for production"
- Mentions "testing passed" or "QA approved"
- Wants to "deploy the release" or "ship it"
- Asks about "finishing the release"
- Says "mark the release as done"

## Output

```
==================================================
COMPLETE RELEASE
==================================================
✓ SUCCESS

Version: 1.2.0

Actions:
  • Found release: 1.2.0
  • Marked release as deployed: 3 tasks completed
  • Merged release/1.2.0 to main
  • Created tag: v1.2.0
  • Merged release/1.2.0 back to develop
  • Deleted branch: release/1.2.0

Tasks (3):
  • [42] Add user authentication
  • [43] Fix login timeout bug
  • [44] Update dashboard layout
```

## Git Operations (with --merge)

When using `--merge`, the script:
1. Merges `release/<version>` to `main`
2. Creates tag `v<version>`
3. Pushes tag to origin
4. Merges `release/<version>` back to `develop`
5. Optionally deletes the release branch

## Prerequisites

- Release must exist in "testing" status
- Dev Tracker API configured
- Git access for merge operations (if using --merge)
