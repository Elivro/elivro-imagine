# ElivroImagine

Voice-to-backlog tool for Elivro development. Press a hotkey to record your thoughts, get them transcribed locally with Whisper, and save to markdown files for later processing with Claude Code.

## Installation

### Prerequisites

- Python 3.10+
- FFmpeg (for Whisper audio processing)

Install FFmpeg on Windows:
```bash
winget install FFmpeg
```

### Install ElivroImagine

```bash
cd C:\Users\jimmy\Projects\personal-productivity
pip install -e .
```

## Usage

### Run the app

```bash
python -m elivroimagine
```

Or after installation:
```bash
elivroimagine
```

### Recording

- **Default hotkey**: `Ctrl+Alt+R`
- **Hold mode** (default): Hold the hotkey to record, release to stop
- **Toggle mode**: Press once to start, press again to stop

### Settings

Right-click the system tray icon and select "Settings" to:
- Change the hotkey
- Switch between hold/toggle recording modes
- Select Whisper model size (tiny/base/small/medium)
- Change transcriptions folder
- Enable start with Windows

### Output

Transcriptions are saved to `~/.elivroimagine/transcriptions/` as markdown files:

```markdown
---
timestamp: 2026-02-01 10:45:23
duration: 12.5s
---

Your transcribed voice note here...
```

### Processing with Claude Code

When ready to process your transcriptions into tasks, ask Claude Code:

> "Read my transcriptions in ~/.elivroimagine/transcriptions/ and create a structured task list organized by theme"

Claude Code will read the files and can generate a `tasks.md` with organized, actionable items.

## Configuration

Config file: `~/.elivroimagine/config.yaml`

```yaml
hotkey:
  combination: "<ctrl>+<alt>+r"
  mode: "hold"  # or "toggle"

recording:
  sample_rate: 16000
  max_duration_seconds: 120

whisper:
  model_size: "small"
  language: "en"

storage:
  transcriptions_dir: "~/.elivroimagine/transcriptions"

startup:
  start_with_windows: false
```

## Model Sizes

| Model  | Size   | RAM    | Speed    |
|--------|--------|--------|----------|
| tiny   | ~39MB  | ~1GB   | Fastest  |
| base   | ~74MB  | ~1GB   | Fast     |
| small  | ~244MB | ~2GB   | Moderate |
| medium | ~769MB | ~5GB   | Slower   |

The "small" model is recommended for good accuracy without excessive resource usage.
