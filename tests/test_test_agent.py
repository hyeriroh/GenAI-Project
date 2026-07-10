from datetime import datetime

import pytest

from english_news_agent.test_agent import (
    GradeResult,
    QuestionType,
    SourceNote,
    VocabCandidate,
    VocabQuestion,
    apply_answer_to_test_markdown,
    build_test_history_entry,
    build_vocab_questions,
    build_vocab_test_markdown,
    extract_vocab_candidates,
    grade_answer,
    select_vocab_candidates,
    test_filename as make_test_filename,
    update_history_markdown,
)


ARTICLE_NOTE = """# Article

## Useful Expressions

- **point of debate**: 논쟁거리
  Example: Hybrid work remains a point of debate.

## Vocabulary

| Word | Part of Speech | Korean Meaning | Example |
| --- | --- | --- | --- |
| breach | noun | 위반, 침해 | The attack may breach international law. |
| defiant | adjective | 굴복하지 않는 | The leader remained defiant. |

## Phrases and Collocations

| Phrase | Korean Meaning | Example |
| --- | --- | --- |
| measure productivity | 생산성을 측정하다 | Companies measure productivity in new ways. |
"""


def test_extract_vocab_candidates_reads_note_sections():
    note = SourceNote("2026-07-10_article.md", ARTICLE_NOTE)

    candidates = extract_vocab_candidates(note)

    assert {candidate.term for candidate in candidates} == {
        "breach",
        "defiant",
        "measure productivity",
        "point of debate",
    }
    breach = next(candidate for candidate in candidates if candidate.term == "breach")
    assert breach.part_of_speech == "noun"
    assert breach.source_section == "Vocabulary"


def test_select_vocab_candidates_prioritizes_history_misses():
    notes = [SourceNote("recent.md", ARTICLE_NOTE)]
    history = """# English News Vocabulary Test History

## Weak Vocabulary

| Word | Missed | Last Seen | Notes |
| --- | ---: | --- | --- |
| defiant | 3 | 2026-07-10 | often confused |
"""

    selected = select_vocab_candidates(notes, history, limit=2)

    assert selected[0].term == "defiant"
    assert selected[0].missed_count == 3


def test_build_vocab_test_markdown_contains_questions_and_policy():
    created_at = datetime(2026, 7, 10, 21, 30)
    candidates = [
        VocabCandidate(
            term="breach",
            meaning_ko="위반하다",
            source_note="article.md",
            source_section="Vocabulary",
            example_sentence="The attack may breach international law.",
        )
    ]

    markdown = build_vocab_test_markdown(candidates, created_at)

    assert "status: in_progress" in markdown
    assert "# Vocabulary Test - 2026-07-10 21:30" in markdown
    assert "- source: [[article]]" in markdown
    assert "- correct_answer: 위반하다" in markdown
    assert "## Review Needed" in markdown


def test_grade_answer_scores_meaning_overlap():
    question = VocabQuestion(
        id=1,
        candidate=VocabCandidate(
            term="breach",
            meaning_ko="법을 위반하다",
            source_note="article.md",
            source_section="Vocabulary",
        ),
        question_type=QuestionType.MEANING,
        prompt="What does breach mean?",
        correct_answer="법을 위반하다",
    )

    assert grade_answer(question, "법을 위반하다").result == "correct"
    assert grade_answer(question, "위반하다").result == "partial"
    assert grade_answer(question, "찬성하다").result == "incorrect"


def test_grade_answer_scores_reverse_questions():
    question = VocabQuestion(
        id=1,
        candidate=VocabCandidate(
            term="defiant",
            meaning_ko="굴복하지 않는",
            source_note="article.md",
            source_section="Vocabulary",
        ),
        question_type=QuestionType.REVERSE,
        prompt="Write the English word.",
        correct_answer="defiant",
    )

    assert grade_answer(question, "defiant") == GradeResult("correct", "Correct.", 1)
    assert grade_answer(question, "defiance").result == "incorrect"


def test_apply_answer_to_test_markdown_updates_question_block():
    candidate = VocabCandidate(
        term="breach",
        meaning_ko="위반하다",
        source_note="article.md",
        source_section="Vocabulary",
    )
    markdown = build_vocab_test_markdown([candidate], datetime(2026, 7, 10, 21, 30))
    grade = GradeResult("partial", "Close answer.", 0.5)

    updated = apply_answer_to_test_markdown(markdown, 1, "깨다", grade)

    assert "- user_answer: 깨다" in updated
    assert "- result: partial" in updated
    assert "- feedback: Close answer." in updated


def test_history_entry_and_update_history_markdown():
    candidate = VocabCandidate(
        term="breach",
        meaning_ko="위반하다",
        source_note="article.md",
        source_section="Vocabulary",
    )
    questions = build_vocab_questions([candidate])
    entry = build_test_history_entry(
        "2026-07-10_2130_vocab-test.md",
        questions,
        [GradeResult("incorrect", "Review it.", 0)],
        datetime(2026, 7, 10, 21, 45),
    )

    history = update_history_markdown("", entry)

    assert "| 2026-07-10 | [[2026-07-10_2130_vocab-test]] | 0 | 1 |" in history
    assert "breach" in history


def test_test_filename_is_timestamped():
    assert make_test_filename(datetime(2026, 7, 10, 21, 30)) == "2026-07-10_2130_vocab-test.md"


def test_apply_answer_to_missing_question_raises():
    with pytest.raises(ValueError):
        apply_answer_to_test_markdown("## Questions\n", 99, "answer", GradeResult("correct", "ok", 1))
