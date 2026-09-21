"""
Configuration manager for MuMuRealRun.
Loads settings from YAML files, applies defaults, and merges command line overrides.
"""

import os
from typing import Dict, Any, Optional
import yaml

DEFAULT_CONFIG: Dict[str, Any] = {
    "mumu": {
        "path": "",
        "vm_index": 0,
        "auto_launch": True,
        "backend": "mumu_manager",
    },
    "run": {
        "route_file": "ZJGroute.txt",
        "coord_type": "gcj02",
        "speed_mps": 3.2,
        "speed_jitter_pct": 0.10,
        "gps_jitter_meters": 0.8,
        "slow_down_on_turns": True,
        "interval_sec": 1.0,
    },
    "target": {
        "distance_meters": 0,
        "laps": 0,
        "infinite_loop": True,
    },
    "adb": {
        "auto_connect": True,
        "target_package": "net.crigh.mysport",
    },
}


class Config:
    """Wraps loaded configuration dictionary."""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data = self._deep_merge(DEFAULT_CONFIG, data or {})

    @classmethod
    def load_from_file(cls, filepath: str = "config.yaml") -> "Config":
        """Load configuration from a YAML file if exists, else return defaults."""
        if os.path.isfile(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return cls(data)
            except Exception as e:
                print(f"[Warning] Failed to read {filepath} ({e}), falling back to default settings.")
        return cls()

    @staticmethod
    def _deep_merge(base: dict, update: dict) -> dict:
        """Deep merge two dictionaries."""
        merged = base.copy()
        for k, v in update.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = Config._deep_merge(merged[k], v)
            else:
                merged[k] = v
        return merged

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve top-level or nested config using dot notation (e.g. 'mumu.vm_index')."""
        parts = key.split(".")
        val = self._data
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                return default
        return val

    def set(self, key: str, value: Any):
        """Set nested config value using dot notation."""
        parts = key.split(".")
        val = self._data
        for p in parts[:-1]:
            if p not in val or not isinstance(val[p], dict):
                val[p] = {}
            val = val[p]
        val[parts[-1]] = value

    @property
    def data(self) -> Dict[str, Any]:
        return self._data
