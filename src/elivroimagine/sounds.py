"""Audio feedback sounds for recording start/stop."""

import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Sound files location
SOUNDS_DIR = Path(__file__).parent / "sounds"
START_SOUND = SOUNDS_DIR / "start.mp3"
STOP_SOUND = SOUNDS_DIR / "stop.mp3"

# Volume adjustment factors (to normalize volumes)
# Start sound was at 70%, so boost by ~1.43x (100/70)
START_VOLUME = 1.0  # pygame volume 0.0-1.0, we'll set it to max
STOP_VOLUME = 0.7   # Stop sound is at 100%, reduce to match start

_mixer_initialized = False


def _ensure_mixer() -> bool:
    """Initialize pygame mixer if not already done."""
    global _mixer_initialized
    if _mixer_initialized:
        return True

    try:
        import pygame
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        _mixer_initialized = True
        logger.debug("pygame mixer initialized")
        return True
    except Exception as e:
        logger.warning(f"Failed to initialize audio mixer: {e}")
        return False


def _play_sound_thread(sound_path: Path, volume: float) -> None:
    """Play a sound file in a thread."""
    try:
        import pygame

        if not _ensure_mixer():
            return

        if not sound_path.exists():
            logger.warning(f"Sound file not found: {sound_path}")
            return

        sound = pygame.mixer.Sound(str(sound_path))
        sound.set_volume(volume)
        sound.play()

    except Exception as e:
        logger.debug(f"Failed to play sound {sound_path}: {e}")


def play_start_sound() -> None:
    """Play the recording start sound (non-blocking)."""
    threading.Thread(
        target=_play_sound_thread,
        args=(START_SOUND, START_VOLUME),
        daemon=True
    ).start()


def play_stop_sound() -> None:
    """Play the recording stop sound (non-blocking)."""
    threading.Thread(
        target=_play_sound_thread,
        args=(STOP_SOUND, STOP_VOLUME),
        daemon=True
    ).start()
