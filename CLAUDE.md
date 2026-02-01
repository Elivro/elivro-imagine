# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ElivroImagine is a Windows voice-to-backlog tool that records voice notes via global hotkey, transcribes them locally with OpenAI Whisper, and saves to markdown files. Transcriptions are processed into structured tasks manually via Claude Code (no API costs).

## Commands

```bash
# Install (editable mode)
pip install -e .

# Run the app
python -m elivroimagine

# Prerequisites: FFmpeg required for Whisper
winget install FFmpeg
```

## Architecture

The app follows an event-driven architecture with `ElivroImagineApp` (app.py) as the central orchestrator.

**Data Flow**: Hotkey press → AudioRecorder captures audio → Transcriber converts to text → StorageManager saves markdown

**Component Responsibilities**:
- `app.py`: Orchestrates all components, handles callbacks between them, manages threading
- `config.py`: Dataclass-based config with YAML persistence at `~/.elivroimagine/config.yaml`
- `hotkey.py`: Global hotkey via pynput with hold/toggle modes
- `recorder.py`: Audio capture via soundcard library at 16kHz mono
- `transcriber.py`: Local Whisper inference with lazy model loading
- `storage.py`: Markdown files with YAML frontmatter at `~/.elivroimagine/transcriptions/`
- `tray.py`: System tray via pystray with recording state indicator
- `settings_ui.py`: tkinter settings window launched from tray

**Threading Model**: Main thread runs event loop. Hotkey listener, tray icon, and transcription each run in separate daemon threads. Settings window runs in its own thread to avoid blocking.

**Runtime Files** (created at `~/.elivroimagine/`):
- `config.yaml` - User settings
- `transcriptions/*.md` - Voice note transcriptions
- `transcriptions/archive/` - Processed transcriptions
- `logs/elivroimagine.log` - Application logs

## Session Startup

1. **Load Dev Tracker skill**: Read `.claude/skills/dev-tracker/SKILL.md` at the start of every session. This skill tracks development tasks across sessions, logs progress, and detects conflicts. Invoke `/dev-tracker` BEFORE starting any implementation task.

2. Review recent work:
   ```bash
   git log --oneline -5
   git status
   ```

Note: The dev-tracker categories are Elivro-specific but the tool works for any project. Use generic category names or create project-specific ones as needed.

## Critical Reminders

1. **Dev Tracker Mandatory**: BEFORE starting ANY implementation task, invoke `/dev-tracker` to track progress. This includes: fixing bugs, adding features, writing code, refactoring, or executing plans.
2. **Type Safety**: All function parameters and returns must be explicitly typed with Python type hints
3. **No AI Mentions**: Never mention Claude/AI in commits or PRs
4. **Commit Early and Often - Protect Your Work**:
   - **Commit after each logical unit of work** (completed task, passing test, working feature)
   - **Stage new files immediately** with `git add <file>` - untracked files are NOT protected by Git
   - **Before `git rebase`, `git reset`, or `git checkout`**: Run `git stash --include-untracked` or commit WIP
   - Untracked files can be **permanently lost** during these operations - Git cannot recover them
5. **PR Creation** (when creating a PR):
   - **ALWAYS target `develop` branch** using `--base develop` (NOT `main`)
   - Use GitHub CLI to find the correct issue
   - Include closing keyword in PR body (e.g., `Fixes #123`)
   - Link the issue to the PR

## Processing Transcriptions

When asked to process transcriptions into tasks:
1. Read all `.md` files from `~/.elivroimagine/transcriptions/`
2. Extract actionable items and themes
3. Create/update `~/.elivroimagine/tasks.md` with structured task list
4. Move processed transcriptions to `transcriptions/archive/`
