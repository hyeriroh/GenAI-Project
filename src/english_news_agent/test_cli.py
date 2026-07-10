from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from english_news_agent.config import load_config
from english_news_agent.models import AppConfig
from english_news_agent.test_agent import (
    GradeResult,
    SourceNote,
    VocabQuestion,
    apply_answer_to_test_markdown,
    build_test_history_entry,
    build_vocab_questions,
    build_vocab_test_markdown,
    grade_answer,
    select_vocab_candidates,
    test_filename,
    update_history_markdown,
)

InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run an English News vocabulary test from local Obsidian notes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Create and run a vocabulary test.")
    start.add_argument("--config", default="config.yaml", help="Path to config.yaml. config.local.yaml is preferred automatically.")
    start.add_argument("--limit", type=int, default=10, help="Number of questions to generate.")
    start.add_argument("--source-limit", type=int, default=20, help="Number of recent article notes to scan.")
    start.add_argument("--no-llm", action="store_true", help="Use deterministic fallback grading instead of the LLM judge.")

    args = parser.parse_args(argv)
    if args.command == "start":
        config = load_config(args.config)
        test_path = run_vocab_test(
            config=config,
            limit=args.limit,
            source_limit=args.source_limit,
            use_llm=not args.no_llm,
        )
        print(f"Saved test: {test_path}")


def run_vocab_test(
    config: AppConfig,
    limit: int = 10,
    source_limit: int = 20,
    use_llm: bool = True,
    input_func: InputFunc = input,
    output_func: OutputFunc = print,
    now: datetime | None = None,
) -> Path:
    created_at = now or datetime.now()
    news_dir = news_directory(config)
    test_dir = news_dir / "Test"
    test_dir.mkdir(parents=True, exist_ok=True)

    history_path = test_dir / "test-history.md"
    history_markdown = history_path.read_text(encoding="utf-8") if history_path.exists() else ""

    source_notes = load_recent_source_notes(news_dir, source_limit)
    if not source_notes:
        raise RuntimeError(f"No source notes found in {news_dir}")

    candidates = select_vocab_candidates(source_notes, history_markdown, limit=limit)
    if not candidates:
        raise RuntimeError("No vocabulary candidates found in the selected notes.")

    questions = build_vocab_questions(candidates)
    filename = test_filename(created_at)
    test_path = test_dir / filename
    test_markdown = build_vocab_test_markdown(candidates, created_at)
    test_path.write_text(test_markdown, encoding="utf-8")

    grades: list[GradeResult] = []
    for question in questions:
        output_func(f"{question.id}/{len(questions)} {question.prompt}")
        answer = input_func("Your answer: ")
        grade = grade_answer(question, answer, config.study, use_llm=use_llm)
        grades.append(grade)
        output_func(f"{grade.result} ({grade.points:g}) - {grade.feedback}")
        if grade.rationale:
            output_func(f"Reason: {grade.rationale}")
        test_markdown = apply_answer_to_test_markdown(test_markdown, question.id, answer, grade)
        test_path.write_text(test_markdown, encoding="utf-8")

    completed_at = datetime.now() if now is None else created_at
    test_markdown = finalize_test_markdown(test_markdown, questions, grades, completed_at)
    test_path.write_text(test_markdown, encoding="utf-8")

    entry = build_test_history_entry(filename, questions, grades, completed_at)
    history_path.write_text(update_history_markdown(history_markdown, entry), encoding="utf-8")
    output_func(f"Score: {sum(grade.points for grade in grades):g}/{len(questions)}")
    return test_path


def news_directory(config: AppConfig) -> Path:
    return Path(config.obsidian.vault_path).expanduser() / config.obsidian.news_dir


def load_recent_source_notes(news_dir: Path, limit: int = 20) -> list[SourceNote]:
    if not news_dir.exists():
        return []

    note_paths = [
        path
        for path in news_dir.rglob("*.md")
        if "Test" not in path.relative_to(news_dir).parts
    ]
    note_paths.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)

    notes: list[SourceNote] = []
    for path in note_paths[:limit]:
        relative_name = path.relative_to(news_dir).as_posix()
        notes.append(SourceNote(filename=relative_name, content=path.read_text(encoding="utf-8")))
    return notes


def finalize_test_markdown(
    markdown: str,
    questions: Sequence[VocabQuestion],
    grades: Sequence[GradeResult],
    completed_at: datetime,
) -> str:
    correct = sum(1 for grade in grades if grade.result == "correct")
    partial = sum(1 for grade in grades if grade.result == "partial")
    incorrect = sum(1 for grade in grades if grade.result == "incorrect")
    score = sum(grade.points for grade in grades)
    review_terms = [
        question.candidate.term
        for question, grade in zip(questions, grades, strict=False)
        if grade.result != "correct"
    ]

    completed_value = completed_at.strftime('%Y-%m-%d %H:%M')
    replacements = {
        "status: in_progress": "status: completed",
        "completed:": f"completed: {completed_value}",
        "score:": f"score: {score:g} / {len(questions)}",
        "- score:": f"- score: {score:g} / {len(questions)}",
        "- correct:": f"- correct: {correct}",
        "- partial:": f"- partial: {partial}",
        "- incorrect:": f"- incorrect: {incorrect}",
        "- completed:": f"- completed: {completed_value}",
    }
    for old, new in replacements.items():
        markdown = markdown.replace(old, new, 1)

    review_block = "\n".join(f"- {term}" for term in review_terms) or "- "
    if "## Review Needed\n" in markdown:
        before, _sep, _after = markdown.partition("## Review Needed\n")
        markdown = before + "## Review Needed\n" + review_block + "\n"
    return markdown


if __name__ == "__main__":
    main()
