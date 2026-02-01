---
name: Create Release
description: Create a release branch from develop and move ready tasks to testing in Dev Tracker
when_to_use: when ready to create a release, cut a release branch, start a release cycle, deploy to staging, or bundle ready features for testing
version: 1.0.0
---

# Create Release

Creates a release branch from `origin/develop` and registers it in Dev Tracker, moving all "Ready for Release" tasks to "Testing" status.

## Usage

```
/create-release <version>
```

**Examples:**
- `/create-release 1.2.0`
- `/create-release 2.0.0-beta.1`

## Execution

### Step 1: Create the release branch

Run the Python script from repo root:

```bash
cd .claude/skills/dev-tracker/scripts && python release_manager.py create <version>
```

**Options:**
```bash
# With release title
python release_manager.py create 1.2.0 --title "User Dashboard Improvements"

# Preview without making changes
python release_manager.py create 1.2.0 --dry-run
```

### Step 2: Generate changelog

After creating the release branch, checkout the branch and generate the changelog:

```bash
git checkout release/<version>
python .claude/skills/changelog-generator/get_commits.py
```

The script auto-detects the release branch and compares against the previous tag. Use the output to create the changelog file following the changelog-generator skill workflow.

## What It Does

1. Validates semantic version format (e.g., `1.2.0`, `2.0.0-rc.1`)
2. Fetches `origin/develop`
3. Creates branch `release/<version>` from develop
4. Pushes branch to origin
5. Calls API to create release in Dev Tracker
6. Moves all `ready_for_release` tasks to `testing` status
7. Associates tasks with the new release
8. **Generates changelog** by comparing the release branch against the previous tag

## When to Suggest This Skill

Suggest `/create-release` when the user:
- Says "let's create a release" or "cut a release"
- Mentions "ready to deploy to staging"
- Wants to "bundle features for testing"
- Has multiple tasks in "ready for release" status
- Asks about "starting a release cycle"

## Output

```
==================================================
CREATE RELEASE
==================================================
✓ SUCCESS

Version: 1.2.0

Actions:
  • Validated version: 1.2.0
  • Fetched origin
  • Verified origin/develop exists
  • Created branch: release/1.2.0
  • Pushed release/1.2.0 to origin
  • Created release in Dev Tracker: 3 tasks included

Tasks (3):
  • [42] Add user authentication
  • [43] Fix login timeout bug
  • [44] Update dashboard layout
```

After creating the release, the changelog generator output will show:

```
Detected release branch: release/1.2.0
Target version: v1.2.0
Comparing against: v1.1.0

======================================================================
CHANGELOG COMMITS: v1.1.0 (2026-01-15) -> release/1.2.0 (2026-01-30)
======================================================================
...
```

## Prerequisites

- Git repository with `origin/develop` branch
- Dev Tracker API configured (see dev-tracker skill)
- No existing release with same version
