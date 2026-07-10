from english_news_agent.models import (
    ArticleAnalysis,
    CollocationItem,
    ParagraphTranslation,
    SentenceTranslation,
    UsefulExpression,
    VocabularyItem,
    ExpressionLookup,
)
from english_news_agent.renderer import (
    render_article_note,
    render_expression_lookup,
    render_vocabulary_lookup_row,
)


def sample_analysis() -> ArticleAnalysis:
    return ArticleAnalysis(
        title="Hybrid Work Debate",
        paragraph_translations=[
            ParagraphTranslation(
                original="Hybrid work remains a point of debate.",
                korean_translation="하이브리드 근무는 여전히 논쟁거리입니다.",
                sentences=[
                    SentenceTranslation(
                        original="Hybrid work remains a point of debate.",
                        korean_translation="하이브리드 근무는 여전히 논쟁거리입니다.",
                    )
                ],
            )
        ],
        korean_translation="하이브리드 근무에 대한 논쟁입니다.",
        english_summary="Companies and workers are debating hybrid work.",
        korean_summary="회사와 근로자들이 하이브리드 근무를 논의하고 있습니다.",
        key_points=["Hybrid work is a compromise.", "Productivity measures are changing."],
        useful_expressions=[
            UsefulExpression(
                expression="point of debate",
                meaning_ko="논쟁거리",
                example_sentence="Remote work remains a point of debate.",
            )
        ],
        vocabulary=[
            VocabularyItem(
                word="compromise",
                part_of_speech="noun",
                meaning_ko="타협",
                example_sentence="Hybrid work is a compromise.",
            )
        ],
        collocations=[
            CollocationItem(
                phrase="measure productivity",
                meaning_ko="생산성을 측정하다",
                example_sentence="Companies measure productivity in new ways.",
            )
        ],
    )


def test_render_article_note_contains_required_sections():
    markdown = render_article_note(sample_analysis(), "Original text", "https://example.com")

    assert "type: english_news_article" in markdown
    assert "## Original Article" in markdown
    assert "Hybrid work remains a point of debate." in markdown
    assert "Original text" not in markdown
    assert "## 단락별 Translation" in markdown
    assert "### Paragraph 1" in markdown
    assert "하이브리드 근무는 여전히 논쟁거리입니다." in markdown
    assert "**해석:**" not in markdown
    assert "| English Sentence | Korean Translation |" not in markdown
    assert "## Vocabulary" in markdown
    assert "## Expression Lookup Log" in markdown
    assert "## Reading Notes" in markdown


def test_render_sentence_fallback_uses_sentence_labels():
    analysis = sample_analysis()
    analysis.structure_type = "sentence"
    markdown = render_article_note(analysis, "Original text", "https://example.com")

    assert "## 문장별 Translation" in markdown
    assert "### Sentence 1" in markdown
    assert "### Paragraph 1" not in markdown


def test_render_article_note_contains_vocabulary_and_collocation_tables():
    markdown = render_article_note(sample_analysis(), "Original text", "https://example.com")

    assert "| Word | Part of Speech | Korean Meaning | Example |" in markdown
    assert "| measure productivity | 생산성을 측정하다 | Companies measure productivity in new ways. |" in markdown


def test_render_word_lookup_as_vocabulary_row():
    markdown = render_vocabulary_lookup_row(
        ExpressionLookup(
            expression="possibility",
            lookup_type="word",
            natural_translation_ko="가능성",
            explanation_ko="어떤 일이 일어날 수 있는 정도를 뜻합니다.",
            part_of_speech="noun",
            etymology_or_roots="possible + -ity",
            english_definition="A chance that something may happen.",
            synonyms=["chance", "likelihood"],
            antonyms=["impossibility"],
            example_sentences=["There is a possibility of rain."],
        )
    )

    assert markdown == "| possibility | noun | 가능성 | There is a possibility of rain. |"


def test_render_sentence_lookup_uses_study_sections():
    markdown = render_expression_lookup(
        ExpressionLookup(
            expression="The talks have been on pause.",
            lookup_type="sentence",
            natural_translation_ko="회담은 중단된 상태였습니다.",
            sentence_translation_ko="회담은 중단된 상태였습니다.",
            explanation_ko="회담이 진행되지 않고 있다는 뜻입니다.",
            syntax_notes=["The talks가 주어, have been on pause가 술어입니다."],
            grammar_notes=["현재완료는 과거부터 현재까지 이어진 상태를 나타냅니다."],
            difficult_words=["on pause: 중단된 상태인"],
        )
    )

    assert "**해석:** 회담은 중단된 상태였습니다." in markdown
    assert "**구문 설명**" in markdown
    assert "**문법 포인트**" in markdown
    assert "**어려운 단어**" in markdown
    assert "Natural Korean" not in markdown
