from datetime import datetime
from pathlib import Path

from english_news_agent.models import AppConfig, ObsidianConfig
from english_news_agent.test_cli import (
    finalize_test_markdown,
    load_recent_source_notes,
    news_directory,
    run_vocab_test,
)
from english_news_agent.test_agent import (
    GradeResult,
    VocabCandidate,
    apply_answer_to_test_markdown,
    build_vocab_questions,
    build_vocab_test_markdown,
)


ARTICLE = """# Test Article

## Vocabulary

| Word | Part of Speech | Korean Meaning | Example |
| --- | --- | --- | --- |
| breach | verb | 위반하다 | The attack may breach international law. |
| defiant | adjective | 굴복하지 않는 | The leader remained defiant. |

## Useful Expressions

- **point of debate**: 논쟁거리
  Example: The plan remains a point of debate.
"""


def config_for(tmp_path: Path) -> AppConfig:
    return AppConfig(
        obsidian=ObsidianConfig(
            vault_path=str(tmp_path / "vault"),
            news_dir="English News",
            vocab_dir="Vocabulary",
        )
    )


def test_load_recent_source_notes_excludes_test_folder(tmp_path: Path):
    config = config_for(tmp_path)
    news_dir = news_directory(config)
    news_dir.mkdir(parents=True)
    (news_dir / "article.md").write_text(ARTICLE, encoding="utf-8")
    test_dir = news_dir / "Test"
    test_dir.mkdir()
    (test_dir / "old-test.md").write_text("## Vocabulary\n", encoding="utf-8")

    notes = load_recent_source_notes(news_dir)

    assert [note.filename for note in notes] == ["article.md"]


def test_run_vocab_test_creates_test_note_and_history(tmp_path: Path):
    config = config_for(tmp_path)
    news_dir = news_directory(config)
    news_dir.mkdir(parents=True)
    (news_dir / "article.md").write_text(ARTICLE, encoding="utf-8")
    answers = iter(["위반하다", "defiant"])
    output: list[str] = []

    test_path = run_vocab_test(
        config,
        limit=2,
        use_llm=False,
        input_func=lambda _prompt: next(answers),
        output_func=output.append,
        now=datetime(2026, 7, 10, 21, 30),
    )

    assert test_path == news_dir / "Test" / "2026-07-10_2130_vocab-test.md"
    markdown = test_path.read_text(encoding="utf-8")
    assert "status: completed" in markdown
    assert "- user_answer: 위반하다" in markdown
    assert "- rationale:" in markdown
    assert "- score:" in markdown
    assert "completed: 2026-07-10 21:30" in markdown
    history = (news_dir / "Test" / "test-history.md").read_text(encoding="utf-8")
    assert "[[2026-07-10_2130_vocab-test]]" in history
    assert any(line.startswith("Score:") for line in output)


def test_finalize_test_markdown_writes_summary_and_detailed_review_notes():
    candidate = VocabCandidate(
        term="breach",
        meaning_ko="위반하다",
        source_note="article.md",
        source_section="Vocabulary",
    )
    questions = build_vocab_questions([candidate])
    grade = GradeResult("incorrect", "Review it.", 0, "Meaning was not covered.")
    markdown = build_vocab_test_markdown([candidate], datetime(2026, 7, 10, 21, 30))
    markdown = apply_answer_to_test_markdown(markdown, 1, "깨다", grade)

    finalized = finalize_test_markdown(
        markdown,
        questions,
        [grade],
        datetime(2026, 7, 10, 21, 35),
    )

    assert "status: completed" in finalized
    assert "score: 0 / 1" in finalized
    assert "- score: 0 / 1" in finalized
    assert "- incorrect: 1" in finalized
    assert "- completed: 2026-07-10 21:35" in finalized
    assert "## Review Needed\n### breach" in finalized
    assert "- my_answer: 깨다" in finalized
    assert "- correct_answer: 위반하다" in finalized
    assert "- feedback: Review it." in finalized
    assert "- rationale: Meaning was not covered." in finalized
