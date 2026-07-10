from pathlib import Path

from english_news_agent.utils import safe_filename, slugify, unique_path


def test_slugify_generates_ascii_slug():
    assert slugify("The Fed's New Policy: What Changed?") == "the-fed-s-new-policy-what-changed"


def test_safe_filename_removes_unsafe_characters():
    assert safe_filename("Markets / Inflation?.md") == "inflation.md"


def test_unique_path_appends_numeric_suffix(tmp_path: Path):
    existing = tmp_path / "2026-07-08_article.md"
    existing.write_text("already here", encoding="utf-8")

    assert unique_path(existing) == tmp_path / "2026-07-08_article_1.md"

