from english_news_agent.analyzer import _looks_sentence_split, mark_sentence_fallback
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
