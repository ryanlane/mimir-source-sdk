"""Simple JSON-backed settings persistence for Mimir channels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SettingsManager:
    """Persists channel settings to a JSON file in the channel's data directory.

    Usage::

        self.settings = SettingsManager(self.data_dir, defaults={"interval": 60})
        self.settings.get("interval")        # 60
        self.settings.set("interval", 30)
        self.settings.update({"interval": 30, "api_key": "abc"})
        self.settings.all()                  # full dict
    """

    def __init__(self, data_dir: Path, defaults: dict[str, Any] | None = None):
        self._path = data_dir / "settings.json"
        self._defaults = defaults or {}
        self._data: dict[str, Any] = self._load()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def update(self, data: dict[str, Any]) -> None:
        self._data.update(data)
        self._save()

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            try:
                saved = json.loads(self._path.read_text())
                return {**self._defaults, **saved}
            except Exception:
                pass
        return dict(self._defaults)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))
