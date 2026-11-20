"""
talktype/config.py - Centralized configuration loader and schema validator.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

# Base root directory of the application
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")

DEFAULT_CONFIG = {
    "hotkey": "ctrl_r",
    "trigger_mode": "long_press_toggle",
    "long_press_seconds": 1.0,
    "model_size": "small",
    "device": "cpu",
    "compute_type": "int8",
    "language": "auto",
    "auto_format": True,
    "initial_prompt": "Hello! Voice typing in English, বাংলা, or हिन्दी.",
    "paste_mode": "clipboard",
    "restore_clipboard": True,
    "sound_feedback": True,
    "show_overlay": True,
    "sample_rate": 16000
}

def load_config() -> dict:
    """Loads config.json if present, otherwise returns defaults."""
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                cfg.update(user_cfg)
        except Exception as e:
            logger.warning(f"Error reading config.json, using defaults: {e}")
    return cfg

def save_config(config: dict):
    """Safely saves configuration dictionary to config.json."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("Configuration saved successfully.")
    except Exception as e:
        logger.error(f"Error writing config.json: {e}")
