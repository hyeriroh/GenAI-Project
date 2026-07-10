from __future__ import annotations

from datetime import datetime

import yaml

from english_news_agent.models import ArticleAnalysis, ExpressionLookup


def render_article_note(
    analysis: ArticleAnalysis,
    original_article: str,
    source_url: str | None = None,
) -> str:
    frontmatter = {
        "type": "english_news_article",
        "title": analysis.title,
        "created": datetime.now().strftime("%Y-%m-%d"),
        "source_url": source_url or "",
        "tags": ["english", "news", "study"],
    }

    lines = [
        _frontmatter(frontmatter),
        f"# {analysis.title}",
        "",
        "## Original Article",
        "",
        _canonical_original_article(analysis, original_article),
        "",
        _translation_heading(analysis),
        "",
        *_korean_translation_lines(analysis, original_article),
        "",
        "## English Summary",
        "",
        analysis.english_summary.strip(),
        "",
        "## Korean Summary",
        "",
        analysis.korean_summary.strip(),
        "",
        "## Key Points",
        "",
        *_bullet_lines(analysis.key_points),
        "",
        "## Useful Expressions",
        "",
        *_expression_lines(analysis.useful_expressions),
        "",
        "## Vocabulary",
        "",
        "| Word | Part of Speech | Korean Meaning | Example |",
        "| --- | --- | --- | --- |",
        *_vocabulary_rows(analysis),
        "",
        "## Phrases and Collocations",
        "",
        "| Phrase | Korean Meaning | Example |",
        "| --- | --- | --- |",
        *_collocation_rows(analysis),
        "",
        "## Expression Lookup Log",
        "",
        "_New lookups from the app are appended here._",
        "",
        "## Reading Notes",
        "",
        "- [ ] Review difficult sentences",
        "- [ ] Shadow-read the article",
        "- [ ] Rephrase the summary in English",
        "",
    ]
    return "\n".join(lines)


def render_expression_lookup(lookup: ExpressionLookup) -> str:
    lines = [
        f"### {datetime.now().strftime('%Y-%m-%d %H:%M')} - {lookup.expression}",
        "",
        f"**해석:** {lookup.sentence_translation_ko or lookup.natural_translation_ko}",
        "",
        "**구문 설명**",
        "",
        *_bullet_lines(lookup.syntax_notes or [lookup.explanation_ko]),
        "",
        "**문법 포인트**",
        "",
        *_bullet_lines(lookup.grammar_notes),
        "",
        "**어려운 단어**",
        "",
        *_bullet_lines(lookup.difficult_words),
        "",
    ]
    return "\n".join(lines)


def render_vocabulary_lookup_row(lookup: ExpressionLookup) -> str:
    example = lookup.example_sentences[0] if lookup.example_sentences else ""
    return (
        f"| {_cell(lookup.expression)} | {_cell(lookup.part_of_speech)} | "
        f"{_cell(lookup.natural_translation_ko)} | {_cell(example)} |"
    )


def _frontmatter(data: dict) -> str:
    return "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip() + "\n---"


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- "]


def _canonical_original_article(analysis: ArticleAnalysis, original_article: str) -> str:
    if analysis.paragraph_translations:
        paragraphs = [item.original.strip() for item in analysis.paragraph_translations if item.original.strip()]
        if paragraphs:
            return "\n\n".join(paragraphs)
    return ""


def _korean_translation_lines(analysis: ArticleAnalysis, original_article: str) -> list[str]:
    if analysis.paragraph_translations:
        lines: list[str] = []
        for index, item in enumerate(analysis.paragraph_translations, start=1):
            lines.extend(
                [
                    f"### {_unit_label(analysis)} {index}",
                    "",
                    item.original.strip(),
                    "",
                    f"**해석:** {item.korean_translation.strip()}",
                    "",
                ]
            )
        return lines

    paragraphs = [paragraph.strip() for paragraph in original_article.split("\n\n") if paragraph.strip()]
    return [
        line
        for index, paragraph in enumerate(paragraphs, start=1)
        for line in [f"### {_unit_label(analysis)} {index}", "", paragraph, "", "**해석:** ", ""]
    ]


def _translation_heading(analysis: ArticleAnalysis) -> str:
    if analysis.structure_type == "sentence":
        return "## 문장별 Translation"
    return "## 단락별 Translation"


def _unit_label(analysis: ArticleAnalysis) -> str:
    if analysis.structure_type == "sentence":
        return "Sentence"
    return "Paragraph"


def _expression_lines(expressions) -> list[str]:
    if not expressions:
        return ["- "]
    return [
        f"- **{item.expression}**: {item.meaning_ko}  \n  Example: {item.example_sentence}"
        for item in expressions
    ]


def _vocabulary_rows(analysis: ArticleAnalysis) -> list[str]:
    return [
        f"| {_cell(item.word)} | {_cell(item.part_of_speech)} | {_cell(item.meaning_ko)} | {_cell(item.example_sentence)} |"
        for item in analysis.vocabulary
    ]


def _collocation_rows(analysis: ArticleAnalysis) -> list[str]:
    return [
        f"| {_cell(item.phrase)} | {_cell(item.meaning_ko)} | {_cell(item.example_sentence)} |"
        for item in analysis.collocations
    ]


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")
