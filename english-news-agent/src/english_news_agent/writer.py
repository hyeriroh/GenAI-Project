from __future__ import annotations

from pathlib import Path

from english_news_agent.models import AppConfig, ArticleAnalysis, ExpressionLookup
from english_news_agent.renderer import (
    render_article_note,
    render_expression_lookup,
    render_vocabulary_lookup_row,
)
from english_news_agent.utils import slugify, today_string, unique_path


def build_output_path(
    analysis: ArticleAnalysis,
    config: AppConfig,
    output_dir: str | Path | None = None,
) -> Path:
    date_prefix = today_string(config.timezone)
    slug = slugify(analysis.title)
    if output_dir:
        news_dir = Path(output_dir).expanduser()
    else:
        vault = Path(config.obsidian.vault_path).expanduser()
        news_dir = vault / config.obsidian.news_dir
    article_path = news_dir / f"{date_prefix}_{slug}.md"
    return unique_path(article_path)


def write_notes(
    analysis: ArticleAnalysis,
    original_article: str,
    config: AppConfig,
    source_url: str | None = None,
    output_dir: str | Path | None = None,
) -> Path:
    article_path = build_output_path(analysis, config, output_dir)
    article_path.parent.mkdir(parents=True, exist_ok=True)

    article_markdown = render_article_note(analysis, original_article, source_url)

    article_path.write_text(article_markdown, encoding="utf-8")
    return article_path


def append_expression_lookup(note_path: str | Path, lookup: ExpressionLookup) -> Path:
    path = Path(note_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Article note not found: {path}")

    content = path.read_text(encoding="utf-8")
    if lookup.lookup_type == "word":
        content = append_vocabulary_row(content, lookup)
        path.write_text(content, encoding="utf-8")
        return path

    rendered_lookup = render_expression_lookup(lookup)
    marker = "## Expression Lookup Log"

    if marker not in content:
        content = content.rstrip() + f"\n\n{marker}\n\n"

    insert_at = content.find("## Reading Notes")
    if insert_at == -1:
        content = content.rstrip() + "\n\n" + rendered_lookup
    else:
        content = content[:insert_at].rstrip() + "\n\n" + rendered_lookup + "\n" + content[insert_at:]

    path.write_text(content, encoding="utf-8")
    return path


def append_vocabulary_row(content: str, lookup: ExpressionLookup) -> str:
    row = render_vocabulary_lookup_row(lookup)
    next_section = content.find("\n## Phrases and Collocations")
    if next_section == -1:
        return content.rstrip() + "\n\n## Vocabulary\n\n| Word | Part of Speech | Korean Meaning | Example |\n| --- | --- | --- | --- |\n" + row + "\n"

    before = content[:next_section].rstrip()
    after = content[next_section:]
    return before + "\n" + row + "\n" + after
