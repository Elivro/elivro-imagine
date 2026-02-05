# ElivroImagine

Voice-to-backlog tool for the Elivro team. Press a hotkey to record your thoughts, get them transcribed with Whisper, and save to markdown or create DevTracker tasks automatically.

## Quick Start

### Prerequisites

- **Python 3.10+**
- **FFmpeg** (required for Whisper audio processing)
- **Git**

Install FFmpeg on Windows:

```bash
winget install FFmpeg
```

Verify FFmpeg is available:

```bash
ffmpeg -version
```

### Install

```bash
git clone https://github.com/Elivro/elivro-imagine.git
cd elivro-imagine
pip install -e ".[windows]"
```

> The `[windows]` extra installs `pywin32` for Start Menu shortcut support.

### Create Start Menu Shortcut (optional)

```bash
python -m elivroimagine --install
```

### Run

```bash
python -m elivroimagine
```

The app starts in the system tray. Right-click the tray icon for options, or double-click to open Settings.

## Features

### Save Hotkey (voice to file)

Record a voice note and save it as a markdown file.

- **Default hotkey**: `Ctrl+Alt+R`
- **Hold mode** (default): Hold to record, release to stop
- **Toggle mode**: Press once to start, press again to stop

Transcriptions are saved to `~/.elivroimagine/transcriptions/` as markdown with YAML frontmatter:

```markdown
---
timestamp: 2026-02-01 10:45:23
duration: 12.5s
---

Your transcribed voice note here...
```

### Paste Hotkey (voice to clipboard)

Record and paste the transcription directly into the focused text field.

- **Default hotkey**: `Shift+Middle Mouse`
- Useful for quickly dictating into any input field

### DevTracker Hotkey (project task)

Record a voice note, classify it with AI, and create a task in DevTracker automatically.

- **Default hotkey**: `Ctrl+Alt+I`
- Classifies transcription into title, description, category, priority, and effort
- Creates the task on a configurable project (default: `intranet`)
- Requires DevTracker connection to be configured first

## Settings

Open Settings from the tray icon (right-click > Settings, or double-click).

### Hotkeys

Configure key combinations, hold/toggle mode, and scan codes for layout-independent keys (e.g. `§` on Swedish keyboards).

### Transcription

| Backend | Description |
|---------|-------------|
| **Local (Whisper)** | Runs on your machine, no network needed. Recommended. |
| **Berget AI** | Cloud transcription via Berget API. Requires API key. |

### Whisper Model Sizes

| Model  | Size   | RAM    | Speed    | Accuracy |
|--------|--------|--------|----------|----------|
| tiny   | ~39MB  | ~1GB   | Fastest  | Basic    |
| base   | ~74MB  | ~1GB   | Fast     | Good     |
| small  | ~244MB | ~2GB   | Moderate | Better   |
| medium | ~769MB | ~5GB   | Slower   | Best     |

The **small** model is the default and recommended for most use cases.

### DevTracker Connection

Connect to the Elivro DevTracker API for automatic task creation:

- **API URL**: DevTracker API endpoint
- **API Key**: Your team API key
- **Email**: Your developer email
- **Project**: Default project slug

### Sound Feedback

Configurable start/stop recording sounds with volume control.

## Configuration

All settings are stored in `~/.elivroimagine/config.yaml`. You can edit this file directly or use the Settings UI.

```yaml
hotkey:
  combination: "<ctrl>+<alt>+r"
  mode: "hold"

paste_hotkey:
  enabled: false
  combination: "<shift>+<mouse_middle>"
  mode: "hold"

devtracker_hotkey:
  enabled: false
  combination: "<ctrl>+<alt>+i"
  mode: "hold"
  project: "intranet"

recording:
  sample_rate: 16000
  max_duration_seconds: 120

whisper:
  model_size: "small"
  language: "auto"

transcription:
  backend: "local"

devtracker:
  enabled: false
  api_url: "https://basen.elivro.se/internal/api/dev-tracker"

storage:
  transcriptions_dir: "~/.elivroimagine/transcriptions"

startup:
  start_with_windows: false
```

## Runtime Files

All runtime data is stored in `~/.elivroimagine/`:

| Path | Description |
|------|-------------|
| `config.yaml` | User settings |
| `transcriptions/` | Saved voice notes |
| `transcriptions/archive/` | Processed transcriptions |
| `logs/elivroimagine.log` | Application logs |
| `app.lock` | Single-instance lock file |

## Processing Transcriptions

To process saved voice notes into structured tasks, ask Claude Code:

> "Read my transcriptions in ~/.elivroimagine/transcriptions/ and create a structured task list organized by theme"

## Development

### Setup

```bash
git clone https://github.com/Elivro/elivro-imagine.git
cd elivro-imagine
pip install -e ".[dev,windows]"
```

### Run Tests

```bash
python -m pytest tests/
```

### Project Structure

```
src/elivroimagine/
  app.py              # Central orchestrator
  config.py           # Dataclass config with YAML persistence
  hotkey.py           # Global hotkey listener (pynput)
  recorder.py         # Audio capture (sounddevice, 16kHz mono)
  transcriber.py      # Whisper inference (faster-whisper)
  classifier.py       # Task classification via Berget AI (Mistral)
  devtracker.py       # DevTracker REST API client
  paster.py           # Clipboard paste via Win32 API
  storage.py          # Markdown file storage
  tray.py             # System tray icon (pystray)
  settings_ui.py      # Settings window (tkinter)
  splash.py           # Startup splash screen
  utilities.py        # Single-instance lock, disk checks
  windows_integration.py  # Autostart, Start Menu shortcut
  sounds/             # Recording feedback sounds
  assets/             # App icon (PNG, ICO)
```

## Troubleshooting

### "FFmpeg not found"

Make sure FFmpeg is installed and on your PATH:

```bash
winget install FFmpeg
```

Restart your terminal after installing.

### No sound from microphone

Check that your microphone is set as the default recording device in Windows Sound Settings. You can also select a specific microphone in the app settings.

### Hotkey not working

- Make sure the app is running (check system tray)
- Try a different key combination in Settings - some combos may conflict with other apps
- On Swedish keyboards, use the scan code option for the `§` key

### Start Menu shortcut not appearing

Make sure `pywin32` is installed:

```bash
pip install pywin32
python -m elivroimagine --install
```

## License

MIT
