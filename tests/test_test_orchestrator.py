from datetime import datetime

import pytest

from english_news_agent.obsidian_adapter import MockObsidianAdapter
from english_news_agent.test_orchestrator import (
    load_recent_source_notes_from_adapter,
    run_vocab_test_session,
)


ARTICLE = """# Article

## Vocabulary

| Word | Part of Speech | Korean Meaning | Example |
| --- | --- | --- | --- |
| breach | verb | 위반하다 | The attack may breach international law. |
| defiant | adjective | 굴복하지 않는 | The leader remained defiant. |
"""


def test_mock_adapter_lists_source_notes_and_excludes_test_folder():
    adapter = MockObsidianAdapter(
        {
            "40 Resources/English News/article.md": ARTICLE,
            "40 Resources/English News/Test/old-test.md": "## Vocabulary\n",
        }
    )

    notes = load_recent_source_notes_from_adapter(adapter, "40 Resources/English News")

    assert [note.filename for note in notes] == ["article.md"]


def test_run_vocab_test_session_uses_adapter_for_files_and_history():
    adapter = MockObsidianAdapter({"40 Resources/English News/article.md": ARTICLE})
    answers = iter(["위반하다", "defiant"])
    output: list[str] = []

    result = run_vocab_test_session(
        adapter=adapter,
        news_dir="40 Resources/English News",
        limit=2,
        use_llm=False,
        input_func=lambda _prompt: next(answers),
        output_func=output.append,
        now=datetime(2026, 7, 10, 21, 30),
    )

    assert result.test_path == "40 Resources/English News/Test/2026-07-10_2130_vocab-test.md"
    assert result.history_path == "40 Resources/English News/Test/test-history.md"
    assert result.score == 2
    assert "40 Resources/English News/Test" in adapter.folders

    test_markdown = adapter.read_note(result.test_path) or ""
    assert "status: completed" in test_markdown
    assert "- user_answer: 위반하다" in test_markdown
    assert "- user_answer: defiant" in test_markdown
    assert "- rationale:" in test_markdown

    history = adapter.read_note(result.history_path) or ""
    assert "[[2026-07-10_2130_vocab-test]]" in history
    assert any(line.startswith("Score: 2/2") for line in output)


def test_run_vocab_test_session_stops_when_no_source_notes():
    adapter = MockObsidianAdapter()

    with pytest.raises(RuntimeError, match="No source notes found"):
        run_vocab_test_session(
            adapter=adapter,
            news_dir="40 Resources/English News",
            use_llm=False,
            input_func=lambda _prompt: "",
            output_func=lambda _message: None,
        )
