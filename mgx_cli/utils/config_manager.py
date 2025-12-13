import os
import yaml
from pathlib import Path

CONFIG_DIR = Path.home() / ".mgx"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

def load_config():
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def save_config(config):
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True)
    with open(CONFIG_FILE, 'w') as f:
        yaml.dump(config, f)

def get_config_value(key):
    config = load_config()
    return config.get(key)

def set_config_value(key, value):
    config = load_config()
    config[key] = value
    save_config(config)
