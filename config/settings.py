import os
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Default data directory
DATA_DIR = PROJECT_ROOT / 'data'

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database path configuration
# Use environment variable if set, otherwise default to data/profiles.db
DEFAULT_DB_PATH = DATA_DIR / 'profiles.db'
DATABASE_PATH = Path(os.environ.get('GROK_ANALYZER_DB_PATH', DEFAULT_DB_PATH))

# Ensure the directory for the database exists
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Example other config (can be added later)
# LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO') 