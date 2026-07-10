from english_news_agent.analyzer import (
    _looks_sentence_split,
    article_sentences_match,
    build_sentence_fallback_analysis,
    mark_sentence_fallback,
)
from english_news_agent.models import ArticleAnalysis, ParagraphTranslation


def analysis_with_paragraphs(paragraphs: list[str]) -> ArticleAnalysis:
    return ArticleAnalysis(
        title="Test",
        paragraph_translations=[
            ParagraphTranslation(original=paragraph, korean_translation="해석")
            for paragraph in paragraphs
        ],
        korean_translation="전체 해석",
        english_summary="Summary",
        korean_summary="요약",
    )


def test_detects_sentence_by_sentence_paragraphs():
    analysis = analysis_with_paragraphs([f"Sentence {index}." for index in range(13)])

    assert _looks_sentence_split(analysis)


def test_allows_meaning_based_grouped_paragraphs():
    analysis = analysis_with_paragraphs(
        [
            "Sentence one. Sentence two. Sentence three.",
            "Sentence four. Sentence five.",
            "Sentence six. Sentence seven. Sentence eight.",
        ]
    )

    assert not _looks_sentence_split(analysis)


def test_mark_sentence_fallback_sets_structure_type():
    analysis = analysis_with_paragraphs(["Sentence one."])

    marked = mark_sentence_fallback(analysis)

    assert marked.structure_type == "sentence"


def test_article_sentences_match_allows_regrouped_original_sentences():
    article = "First sentence. Second sentence. Third sentence."
    analysis = analysis_with_paragraphs([
        "First sentence. Second sentence.",
        "Third sentence.",
    ])

    assert article_sentences_match(article, analysis)


def test_article_sentences_match_rejects_missing_or_reordered_sentences():
    article = "First sentence. Second sentence. Third sentence."

    assert not article_sentences_match(article, analysis_with_paragraphs(["First sentence. Third sentence."]))
    assert not article_sentences_match(article, analysis_with_paragraphs(["Second sentence. First sentence. Third sentence."]))


def test_build_sentence_fallback_preserves_source_sentence_order():
    article = "First sentence. Second sentence. Third sentence."
    analysis = analysis_with_paragraphs(["First sentence. Third sentence."])

    fallback = build_sentence_fallback_analysis(analysis, article)

    assert fallback.structure_type == "sentence"
    assert [item.original for item in fallback.paragraph_translations] == [
        "First sentence.",
        "Second sentence.",
        "Third sentence.",
    ]
