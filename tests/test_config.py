from pathlib import Path

import pytest

from english_news_agent.config import load_config, resolve_config_path


BASE_CONFIG = """timezone: Asia/Seoul

obsidian:
  vault_path: ./obsidian-vault
  news_dir: English News
  vocab_dir: Vocabulary
"""

LOCAL_CONFIG = """timezone: Asia/Seoul

obsidian:
  vault_path: /private/local-vault
  news_dir: 40 Resources/English News
  vocab_dir: 40 Resources/Vocabulary
"""


def test_resolve_config_path_prefers_config_local(tmp_path: Path):
    config = tmp_path / "config.yaml"
    local = tmp_path / "config.local.yaml"
    config.write_text(BASE_CONFIG, encoding="utf-8")
    local.write_text(LOCAL_CONFIG, encoding="utf-8")

    assert resolve_config_path(config) == local


def test_load_config_uses_config_local_when_present(tmp_path: Path):
    config = tmp_path / "config.yaml"
    local = tmp_path / "config.local.yaml"
    config.write_text(BASE_CONFIG, encoding="utf-8")
    local.write_text(LOCAL_CONFIG, encoding="utf-8")

    loaded = load_config(config)

    assert loaded.obsidian.vault_path == "/private/local-vault"
    assert loaded.obsidian.news_dir == "40 Resources/English News"


def test_resolve_config_path_raises_for_missing_config(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        resolve_config_path(tmp_path / "missing.yaml")
