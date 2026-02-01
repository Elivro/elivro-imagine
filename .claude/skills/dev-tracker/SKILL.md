---
name: Dev Tracker
description: Track development tasks across Claude Code sessions with progress, milestones, and conflict detection
when_to_use: when starting any implementation task, writing code, fixing bugs, adding features, or making code changes - invoke BEFORE beginning the work
version: 1.0.0
---

# Dev Tracker Skill

Track development tasks across Claude Code sessions with a shared team board.

## Commands

| Command | Description |
|---------|-------------|
| `/task-status` | Show current task and milestones |
| `/tasks` | List your active tasks |
| `/mark-ready` | Commit, merge to develop, mark task ready (Python) |
| `/force-new` | Create new task, bypass matching |
| `/rename-task <title>` | Rename current task |
| `/backlog` | List backlog tasks |
| `/backlog-add <title>` | Create backlog task |
| `/backlog-import [file]` | Import tasks from JSON file |
| `/move-to-backlog` | Move current task to backlog |
| `/delete-task [id]` | Delete task |
| `/create-release <version>` | Create release branch from develop (Python) |
| `/complete-release [version]` | Complete release, deploy tasks (Python) |

## Release Management (Python Scripts)

All release operations run via `release_manager.py` for fast, deterministic execution.

### Quick Reference

```bash
# From repo root:
cd .claude/skills/dev-tracker/scripts

# Create release
python release_manager.py create 1.2.0

# Complete release (active)
python release_manager.py complete

# Complete specific version with merge
python release_manager.py complete 1.2.0 --merge --delete-branch

# Mark task ready
python release_manager.py mark-ready

# Mark ready with options
python release_manager.py mark-ready -m "Commit message" --delete-branch

# Check release status
python release_manager.py status
```

### Script Options

**create** `<version>`:
- `--title "Title"` - Release title
- `--dry-run` - Preview only

**complete** `[version]`:
- `--merge` - Merge to main, tag, merge back to develop
- `--delete-branch` - Delete release branch
- `--dry-run` - Preview only

**mark-ready**:
- `--task-id ID` - Specify task (default: active)
- `-m "message"` - Commit message
- `--summary "text"` - Task summary
- `--no-merge` - Skip merge to develop
- `--delete-branch` - Delete feature branch
- `--dry-run` - Preview only

## Task CLI (api.py)

**IMPORTANT: Use these CLI commands directly. Do NOT write inline Python code.**

All commands run from: `cd .claude/skills/dev-tracker/scripts`

```bash
# List your tasks
python api.py tasks

# List all active tasks (check for conflicts)
python api.py active

# Create a new task (ALWAYS include category, priority, effort)
python api.py create "Task title" "Description" --category "Category" --priority medium --effort medium

# Send heartbeat with progress (0-99%)
python api.py heartbeat <task_id> <progress> "Optional note"

# Update task status
python api.py update <task_id> <status> "Optional summary"
# Statuses: backlog, in_progress, ready_for_release, testing, deployed

# Delete a task
python api.py delete <task_id>

# List categories
python api.py categories

# List backlog tasks
python api.py backlog

# Import tasks from JSON file (default: backlog.json)
python api.py batch

# Import from custom file
python api.py batch customer-feedback.json

# Test API connection
python api.py test
```

## Core Behavior

### On Skill Activation

1. Run `python api.py active` to check for conflicts with other developers
2. Run `python api.py tasks` to see your existing assigned tasks
3. **Match the requested work against existing non-deployed tasks:**
   - If user describes work that matches an existing task (any status except `deployed`), continue that task
   - Check backlog with `python api.py backlog` if no assigned task matches
   - Only create new with `python api.py create` if no existing task matches
4. **When creating a new task, ALWAYS include:**
   - `--category` - Pick from the Categories list below based on the feature area
   - `--priority` - Assess urgency (default: medium)
   - `--effort` - Estimate scope (default: medium)

### Task Matching

Before creating a new task, check if the user's request matches an existing task:

| Status | Action |
|--------|--------|
| `backlog` | Pick up the task, assign to yourself |
| `in_progress` (yours) | Continue working on it |
| `in_progress` (others) | Warn about conflict, coordinate |
| `ready_for_release` | Reopen if changes needed |
| `testing` | Reopen if bug found during QA |
| `ready_for_production` | Reopen if last-minute fix needed |
| `deployed` | Create new task (work is complete) |

**Matching criteria:**
- Similar title (case-insensitive, ignore punctuation)
- Related functionality described in task description
- Same feature area/category

If uncertain, ask the user: "I found an existing task '#42: Fix mobile nav' - is this what you want to work on, or is this separate?"

### During Active Task

- **Every few prompts**: `python api.py heartbeat <id> <progress> "note"`
- Progress: 0-10% planning, 10-40% implementing, 40-75% refining, 75-99% reviewing

### Conflict Warning Format

```
⚠️ Potential overlap detected:
Task: "Add user authentication" (assigned to jane@example.com)

Options:
1. Continue anyway (conflict logged)
2. Create separate task with /force-new
3. Coordinate with other developer
```

## Task Status Flow

```
backlog → in_progress → ready_for_release → testing → ready_for_production → deployed
```

## Progress Estimation

Progress: 0-99% (100% reserved for merged tasks)

| Phase | % | Description |
|-------|---|-------------|
| Planning | 0-10 | Understanding, exploring, designing |
| Implementation | 10-40 | Writing core code |
| Feature Complete | 40-60 | Works but needs polish |
| Refinement | 60-75 | Tests, edge cases, cleanup |
| Ready for Review | 75-85 | Code complete, tests passing |
| Addressing Feedback | 85-95 | Fixing review comments |
| Awaiting Merge | 95-99 | Approved, waiting for merge |

### Progress Notes

Max 200 chars. Examples:
- "Implementing core API endpoints"
- "Tests passing, adding error handling"
- "Addressing PR feedback"

## Release Size

Set when creating/finalizing releases:

| Size | Criteria |
|------|----------|
| `tiny` | Single fix, config change |
| `small` | 1-2 tasks, minor tweaks |
| `medium` | 3-5 tasks, new features |
| `large` | 6-10 tasks, significant features |
| `massive` | 10+ tasks, major milestones |

## Categories

Use these predefined categories when creating tasks:

| Category | Color | Description |
|----------|-------|-------------|
| Dashboard | `#3b82f6` | Main recruiter overview page with KPIs, focus zone, activity feed |
| Candidates | `#8b5cf6` | Global kanban board for managing candidates, stage transitions |
| Clients | `#06b6d4` | Client/customer organization management |
| Jobs | `#f59e0b` | Job posting management - creating, editing, listing |
| User Settings | `#6366f1` | User profile settings, preferences, notifications |
| Tenant Admin Settings | `#ec4899` | Organization-level admin settings, theme, user management |
| Public Job Listings | `#10b981` | Public-facing branded job listing pages |
| Onboarding | `#f97316` | First-time user experience, welcome wizard |
| Client Feedback | `#14b8a6` | Client-facing candidate review page |
| Stakeholder | `#a855f7` | Stakeholder views and invitation flows |
| Authentication | `#ef4444` | Login flows, BankID/OIDC, session management |
| AI Matching | `#22d3ee` | AI-powered candidate matching engine |
| System Admin | `#64748b` | Super-admin dashboard, tenant management, analytics |
| Payload Admin | `#84cc16` | Payload CMS admin panel |
| API & Webhooks | `#0ea5e9` | Backend API routes, GraphQL, webhooks |
| Updates / Changelog | `#d946ef` | In-app updates page showing new features |

## Task Priority

| Priority | When to Use |
|----------|-------------|
| `critical` | Security issues, data loss, production blockers |
| `high` | Major UX issues, broken features, customer-reported bugs |
| `medium` | Enhancements, improvements, minor bugs (default) |
| `low` | Nice-to-haves, cosmetic issues, future ideas |

## Task Effort

| Effort | Criteria |
|--------|----------|
| `tiny` | Config change, copy update, single-line fix |
| `small` | 1-2 files, simple logic |
| `medium` | Multiple files, moderate complexity (default) |
| `large` | Feature work, significant changes |
| `massive` | Major feature, architectural changes, multi-day |

## Batch Backlog Import

Import multiple tasks from a JSON file:

```bash
cd .claude/skills/dev-tracker/scripts

# Import from default backlog.json
python api.py batch

# Import from custom file
python api.py batch customer-feedback.json
```

### JSON Format

```json
{
  "tasks": [
    {
      "title": "Add export to CSV feature",
      "description": "Allow users to export candidate data to CSV format",
      "category": "Candidates",
      "priority": "medium",
      "effort": "small"
    },
    {
      "title": "Fix mobile navigation overlay",
      "description": "Navigation menu doesn't close after selection on mobile",
      "category": "Dashboard",
      "priority": "high",
      "effort": "tiny"
    }
  ]
}
```

**Fields:**
- `title` (required): Task title
- `description` (optional): Detailed description
- `category` (optional): Category name (auto-resolved to ID)
- `priority` (optional): low, medium, high, critical (default: medium)
- `effort` (optional): tiny, small, medium, large, massive (default: medium)

### Duplicate Detection

The batch import automatically checks for existing tasks (any status except `deployed`) with similar titles:
- Exact matches after normalization (lowercase, punctuation removed)
- Substring matches with >80% length similarity

Duplicates are skipped and reported:
```
Skipping duplicate: 'Add dark mode' (matches #42: 'Add Dark Mode Toggle' [in_progress])
```

### Automatic Claude Invocation

When user provides a list of tasks/feedback to add to backlog, Claude should:

1. Generate `backlog.json` in scripts folder with proper priority/effort
2. Run: `cd .claude/skills/dev-tracker/scripts && python api.py batch`
3. Report created task IDs

**Trigger phrases**: "add to backlog", "create backlog tasks", "import these tasks", "add these to dev tracker"

## Environment Variables

- `DEV_TRACKER_API_KEY` - Required: Team API key
- `DEV_TRACKER_EMAIL` - Optional: Override git email
- `DEV_TRACKER_API_URL` - Optional: Custom API URL
