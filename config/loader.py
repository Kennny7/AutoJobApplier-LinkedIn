"""
Configuration loader. 
Reads YAML files, substitutes placeholders from user_data.yaml, and returns a unified config dict.
Inputs: paths to defaults.yaml, settings.yaml, user_data.yaml.
Outputs: config dict with all resolved values.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("AutoApply.ConfigLoader")

def load_yaml(file_path: str) -> Dict[str, Any]:
    """Load YAML file, return dictionary."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        logger.debug(f"Loaded config from {file_path}")
        return data
    except FileNotFoundError:
        logger.error(f"Config file not found: {file_path}")
        raise FileNotFoundError(f"Configuration file missing: {file_path}")

def resolve_placeholders(template: str, user_data: dict) -> str:
    """
    Replace %PLACEHOLDER% tokens in template with values from user_data.
    If a key is missing, leave placeholder as is (will be handled later).
    """
    import re
    pattern = r"%([A-Z_]+)%"
    def replacer(match):
        key = match.group(1).lower()
        # Direct mapping
        return str(user_data.get(key, match.group(0)))
    return re.sub(pattern, replacer, template)

def merge_configs(defaults: dict, settings: dict, user_data: dict) -> dict:
    """
    Merge defaults, settings, and user_data into a final config.
    All answer templates are resolved with user_data.
    """
    # Deep copy defaults to avoid mutation
    resolved = defaults.copy()
    # Resolve answer templates in the "answers" section (defaults.yaml)
    # We'll treat the whole defaults as "answers" collection; settings remain separate.
    # For this simple structure, we'll just merge settings into a "config" dict.
    config = {"answers": resolved, "settings": settings, "user": user_data}
    # Resolve placeholders in all strings of answers recursively
    def traverse(obj):
        if isinstance(obj, str):
            return resolve_placeholders(obj, user_data)
        elif isinstance(obj, dict):
            return {k: traverse(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [traverse(elem) for elem in obj]
        else:
            return obj
    config["answers"] = traverse(config["answers"])
    return config

def load_config(defaults_path="config/defaults.yaml",
                settings_path="config/settings.yaml",
                user_data_path="config/user_data.yaml") -> dict:
    """Main function: load all configs and return merged dict."""
    defaults = load_yaml(defaults_path)
    settings = load_yaml(settings_path)
    # Load or create user_data
    if os.path.exists(user_data_path):
        user_data = load_yaml(user_data_path)
    else:
        logger.warning(f"User data file {user_data_path} not found; using empty.")
        user_data = {}
    return merge_configs(defaults, settings, user_data)

def save_user_data(data: dict, path="config/user_data.yaml"):
    """Persist user data to YAML file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)