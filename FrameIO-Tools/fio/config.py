"""
Configuration module for Frame.io CLI
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Load environment variables from .env file
# Look for .env in multiple locations to handle different working directories
env_paths = [
    Path('.') / '.env',  # Current directory
    Path(__file__).parent.parent.parent / '.env',  # FrameIO-Tools root (3 levels up from fio/fio/config.py)
    Path.cwd() / '.env',  # Current working directory
]

# Try each path until we find a .env file
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break
else:
    # Fallback: try loading from environment without file
    load_dotenv()

# Configuration directory and file paths
CONFIG_DIR = Path.home() / '.fio'
CONFIG_FILE = CONFIG_DIR / 'config.json'
CACHE_DIR = CONFIG_DIR / 'cache'
WORKSPACE_CACHE_FILE = CACHE_DIR / 'workspace_cache.json'
FOLDER_HISTORY_FILE = CACHE_DIR / 'folder_history.json'
MAX_HISTORY_ITEMS = 10
DEFAULT_RATE_LIMIT = 10  # Default to 10 requests per minute

def ensure_config_dir():
    """Ensure the configuration directory exists and initialize config file if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                'default_account': None,
                'default_workspace': None,
                'default_project': None,
                'default_folder': None,
                'client_id': None,
                'client_secret': None,
                'rate_limit': DEFAULT_RATE_LIMIT
            }, f, indent=2)

def load_config() -> Dict[str, Any]:
    """Load configuration from the config file."""
    ensure_config_dir()
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Ensure rate_limit is set
            if 'rate_limit' not in config:
                config['rate_limit'] = DEFAULT_RATE_LIMIT
            return config
    except (json.JSONDecodeError, FileNotFoundError):
        # If file is corrupted or doesn't exist, reinitialize it
        ensure_config_dir()
        return {
            'default_account': None,
            'default_workspace': None,
            'default_project': None,
            'default_folder': None,
            'client_id': None,
            'client_secret': None,
            'rate_limit': DEFAULT_RATE_LIMIT
        }

def save_config(config: Dict[str, Any]):
    """Save configuration to the config file."""
    ensure_config_dir()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

# Frame.io API configuration
config = load_config()
FRAME_CLIENT_ID = os.getenv('CLIENT_ID') or config.get('client_id')
FRAME_CLIENT_SECRET = os.getenv('CLIENT_SECRET') or config.get('client_secret')

# API endpoints
TOKEN_URL = 'https://ims-na1.adobelogin.com/ims/token/v3'
API_BASE_URL = 'https://api.frame.io/v4'

def get_default_account():
    """Get the default account ID from the configuration file."""
    config = load_config()
    return config.get('default_account')

def set_default_account(account_id):
    """Set the default account ID in the configuration file."""
    config = load_config()
    config['default_account'] = account_id
    save_config(config)

def get_default_workspace():
    """Get the default workspace ID from the configuration file."""
    config = load_config()
    return config.get('default_workspace')

def set_default_workspace(workspace_id):
    """Set the default workspace ID in the configuration file."""
    config = load_config()
    config['default_workspace'] = workspace_id
    save_config(config)

def get_default_project():
    """Get the default project ID from the configuration file."""
    config = load_config()
    return config.get('default_project')

def set_default_project(project_id):
    """Set the default project ID in the configuration file."""
    config = load_config()
    config['default_project'] = project_id
    save_config(config)

def get_default_folder():
    """Get the default folder ID from the config file."""
    config = load_config()
    return config.get('default_folder')

def set_default_folder(folder_id):
    """Set the default folder ID in the config file."""
    config = load_config()
    config['default_folder'] = folder_id
    save_config(config)

def set_client_credentials(client_id, client_secret):
    """Set the client credentials in the configuration file."""
    config = load_config()
    config['client_id'] = client_id
    config['client_secret'] = client_secret
    save_config(config)

def validate_config():
    """Validate that all required configuration is present."""
    if not FRAME_CLIENT_ID:
        raise ValueError("FRAME_CLIENT_ID not set in environment or config file")
    if not FRAME_CLIENT_SECRET:
        raise ValueError("FRAME_CLIENT_SECRET not set in environment or config file")

def get_rate_limit() -> int:
    """Get the configured rate limit (requests per minute)"""
    config = load_config()
    return config.get('rate_limit', DEFAULT_RATE_LIMIT)

def set_rate_limit(requests_per_minute: int):
    """Set the rate limit (requests per minute)"""
    config = load_config()
    config['rate_limit'] = max(1, requests_per_minute)  # Ensure at least 1 request per minute
    save_config(config) 