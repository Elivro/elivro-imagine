"""Audio feedback sounds for recording start/stop."""

import atexit
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Sound files location
SOUNDS_DIR = Path(__file__).parent / "sounds"
START_SOUND = SOUNDS_DIR / "start.mp3"
STOP_SOUND = SOUNDS_DIR / "stop.mp3"

_mixer_initialized = False
_cached_sounds: dict[str, object] = {}


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


def init_mixer() -> None:
    """Eagerly initialize the mixer and preload sounds into memory.

    Call once at app startup to avoid latency on first play.
    """
    if not _ensure_mixer():
        return

    try:
        import pygame

        for path in (START_SOUND, STOP_SOUND):
            if path.exists():
                _cached_sounds[str(path)] = pygame.mixer.Sound(str(path))
        logger.debug("Sound files preloaded")
    except Exception as e:
        logger.debug(f"Failed to preload sounds: {e}")


def cleanup_mixer() -> None:
    """Clean up pygame mixer resources."""
    global _mixer_initialized
    if _mixer_initialized:
        try:
            import pygame

            pygame.mixer.quit()
            _mixer_initialized = False
            logger.debug("pygame mixer cleaned up")
        except Exception as e:
            logger.debug(f"Failed to cleanup mixer: {e}")


# Register cleanup on module load
atexit.register(cleanup_mixer)


def _play_sound_thread(sound_path: Path, volume: float) -> None:
    """Play a sound file in a thread."""
    try:
        import pygame

        if not _ensure_mixer():
            return

        key = str(sound_path)
        sound = _cached_sounds.get(key)
        if sound is None:
            if not sound_path.exists():
                logger.warning(f"Sound file not found: {sound_path}")
                return
            sound = pygame.mixer.Sound(key)
            _cached_sounds[key] = sound

        sound.set_volume(volume)
        sound.play()

    except Exception as e:
        logger.debug(f"Failed to play sound {sound_path}: {e}")


def play_start_sound(volume: float = 1.0) -> None:
    """Play the recording start sound with configurable volume.

    Args:
        volume: Volume level from 0.0 to 1.0.
    """
    threading.Thread(
        target=_play_sound_thread,
        args=(START_SOUND, volume),
        daemon=True,
    ).start()


def play_stop_sound(volume: float = 0.7) -> None:
    """Play the recording stop sound with configurable volume.

    Args:
        volume: Volume level from 0.0 to 1.0.
    """
    threading.Thread(
        target=_play_sound_thread,
        args=(STOP_SOUND, volume),
        daemon=True,
    ).start()
