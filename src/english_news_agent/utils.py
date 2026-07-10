from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def slugify(text: str, max_length: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return (slug[:max_length].strip("-") or "untitled")


def safe_filename(name: str, suffix: str = ".md") -> str:
    stem = slugify(Path(name).stem)
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return f"{stem}{suffix}"


def today_string(timezone: str = "Asia/Seoul") -> str:
    return datetime.now(ZoneInfo(timezone)).strftime("%Y-%m-%d")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    index = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def obsidian_link_title(filename: str | Path) -> str:
    return Path(filename).stem
