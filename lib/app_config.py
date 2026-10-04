"""Load the app session config that points at device / wifi / library JSON files."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple


def resolve_path(path: str, base_dir: str) -> str:
    """Resolve path relative to base_dir when not absolute."""
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(base_dir, path))


def load_app_config(app_config_path: str, project_root: str) -> Dict[str, Any]:
    """Load app config and resolve nested config paths against project_root.

    Expected shape:
    {
      "device_config": "config/device_....json",
      "wifi_config": "config/wifi_....json",
      "library_config": "config/MyLibrary.json"
    }
    """
    with open(app_config_path) as fh:
        raw = json.load(fh)

    return {
        "app_config_path": os.path.abspath(app_config_path),
        "device_config": resolve_path(raw.get("device_config", ""), project_root),
        "wifi_config": resolve_path(raw.get("wifi_config", ""), project_root),
        "library_config": resolve_path(raw.get("library_config", ""), project_root),
    }


def load_json_file(path: str) -> Optional[Dict[str, Any]]:
    if not path or not os.path.isfile(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def wifi_summary(wifi_config: Optional[Dict[str, Any]]) -> str:
    if not wifi_config:
        return ""
    ssid = wifi_config.get("ssid", "")
    security = wifi_config.get("security", "")
    return f"ssid={ssid!r}, security={security!r}"
