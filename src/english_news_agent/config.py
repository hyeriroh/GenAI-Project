from __future__ import annotations

from pathlib import Path

import yaml

from english_news_agent.models import AppConfig


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = resolve_config_path(path)
    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return AppConfig.model_validate(data)


def resolve_config_path(path: str | Path = "config.yaml") -> Path:
    config_path = Path(path)
    if config_path.name == "config.yaml":
        local_path = config_path.with_name("config.local.yaml")
        if local_path.exists():
            return local_path
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    return config_path

