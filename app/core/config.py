"""应用配置读写（主题、窗口状态等）。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def config_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "FreeScan"
    return Path.home() / ".config" / "FreeScan"


def settings_path() -> Path:
    return config_dir() / "settings.json"


def load_settings() -> Dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_settings(data: Dict[str, Any]) -> None:
    try:
        config_dir().mkdir(parents=True, exist_ok=True)
        path = settings_path()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:  # noqa: BLE001
        pass


def update_setting(key: str, value: Any) -> None:
    data = load_settings()
    data[key] = value
    save_settings(data)
