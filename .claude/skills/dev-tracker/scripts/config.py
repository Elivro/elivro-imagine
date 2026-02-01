"""
Dev Tracker Configuration

Loads settings from a .env file in the scripts directory,
falling back to OS environment variables.
"""

import os
from pathlib import Path
from typing import Optional


def _load_env_file() -> None:
    """Load key=value pairs from .env file into os.environ"""
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        return

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            # Don't override existing env vars
            if key not in os.environ:
                os.environ[key] = value


_load_env_file()

# API Configuration
API_URL: str = os.environ.get(
    'DEV_TRACKER_API_URL',
    'https://intranet.elivro.se/internal/api/dev-tracker'
)

API_KEY: Optional[str] = os.environ.get('DEV_TRACKER_API_KEY')

# Timeout settings (in seconds)
REQUEST_TIMEOUT: int = 30

# Headers template
def get_headers(email: str) -> dict:
    """Get API headers with authentication"""
    if not API_KEY:
        raise ValueError("DEV_TRACKER_API_KEY environment variable not set")

    return {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
        'X-Developer-Email': email,
    }


def validate_config() -> bool:
    """Validate that required configuration is present"""
    if not API_KEY:
        print("Error: DEV_TRACKER_API_KEY environment variable not set")
        return False
    return True
