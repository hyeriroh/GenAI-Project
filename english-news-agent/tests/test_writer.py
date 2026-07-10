from english_news_agent.models import ExpressionLookup
from english_news_agent.models import AppConfig, ArticleAnalysis, ObsidianConfig
from english_news_agent.writer import append_vocabulary_row, build_output_path


def test_append_vocabulary_row_adds_word_before_next_section():
    content = """## Vocabulary

| Word | Part of Speech | Korean Meaning | Example |
| --- | --- | --- | --- |
| existing | adjective | 기존의 | Existing rules apply. |

## Phrases and Collocations
"""
    lookup = ExpressionLookup(
        expression="possibility",
        lookup_type="word",
        natural_translation_ko="가능성",
        explanation_ko="문맥상 가능성을 뜻합니다.",
        part_of_speech="noun",
        example_sentences=["There is a possibility of rain."],
    )

    updated = append_vocabulary_row(content, lookup)

    assert "| possibility | noun | 가능성 | There is a possibility of rain. |" in updated
    assert updated.index("| possibility") < updated.index("## Phrases and Collocations")


def test_build_output_path_uses_override_directory(tmp_path):
    config = AppConfig(
        obsidian=ObsidianConfig(
            vault_path=str(tmp_path / "vault"),
            news_dir="News",
            vocab_dir="Vocabulary",
        )
    )
    analysis = ArticleAnalysis(
        title="Override Directory Test",
        paragraph_translations=[],
        korean_translation="",
        english_summary="",
        korean_summary="",
    )

    path = build_output_path(analysis, config, tmp_path / "custom")

    assert path.parent == tmp_path / "custom"
    assert path.name.endswith("_override-directory-test.md")
