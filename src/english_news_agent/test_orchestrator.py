from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import PurePosixPath
import re
from typing import Callable, Sequence

from english_news_agent.models import StudySettings
from english_news_agent.obsidian_adapter import (
    ObsidianVaultAdapter,
    VaultAdapterError,
    VaultListError,
    VaultReadError,
    VaultWriteError,
)
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


@dataclass(frozen=True)
class VocabTestSessionResult:
    test_path: str | None
    history_path: str
    score: float
    total: int
    warnings: list[str] = field(default_factory=list)
    pending_test_markdown: str = ""
    pending_history_entry: str = ""
    test_note_persisted: bool = True
    history_updated: bool = True


def run_vocab_test_session(
    adapter: ObsidianVaultAdapter,
    news_dir: str,
    study_settings: StudySettings | None = None,
    limit: int = 20,
    source_limit: int = 20,
    batch_size: int = 5,
    use_llm: bool = True,
    input_func: InputFunc = input,
    output_func: OutputFunc = print,
    now: datetime | None = None,
) -> VocabTestSessionResult:
    created_at = now or datetime.now()
    warnings: list[str] = []
    news_dir = _normalize_dir(news_dir)
    test_dir = _join_vault_path(news_dir, "Test")
    try:
        adapter.ensure_folder(test_dir)
    except VaultWriteError as exc:
        raise RuntimeError(f"Could not prepare test folder {test_dir}: {exc}") from exc

    history_path = _join_vault_path(test_dir, "test-history.md")
    try:
        history_markdown = adapter.read_note(history_path) or ""
    except VaultReadError as exc:
        history_markdown = ""
        warnings.append(f"Could not read test history; continuing with empty history: {exc}")

    try:
        source_notes = load_recent_source_notes_from_adapter(adapter, news_dir, source_limit, warnings)
    except VaultListError as exc:
        raise RuntimeError(f"Could not list source notes under {news_dir}: {exc}") from exc
    if not source_notes:
        raise RuntimeError(f"No source notes found in {news_dir}")

    candidates = select_vocab_candidates(source_notes, history_markdown, limit=limit)
    if not candidates:
        raise RuntimeError("No vocabulary candidates found in the selected notes.")

    questions = build_vocab_questions(candidates)
    filename = test_filename(created_at)
    test_path = _join_vault_path(test_dir, filename)
    test_markdown = build_vocab_test_markdown(candidates, created_at)
    test_note_persisted = _try_write_note(adapter, test_path, test_markdown, warnings, "create test note")

    grades: list[GradeResult] = []
    for batch_index, batch in enumerate(_question_batches(questions, batch_size), start=1):
        output_func(f"Batch {batch_index} ({batch[0].id}-{batch[-1].id}/{len(questions)})")
        for question in batch:
            output_func(f"{question.id}. {question.prompt}")
        for question in batch:
            answer = input_func(f"Answer {question.id}: ")
            grade = grade_answer(question, answer, study_settings, use_llm=use_llm)
            grades.append(grade)
            output_func(f"{question.id}: {grade.result} ({grade.points:g}) - {grade.feedback}")
            if grade.rationale:
                output_func(f"Reason: {grade.rationale}")
            test_markdown = apply_answer_to_test_markdown(test_markdown, question.id, answer, grade)
            if test_note_persisted:
                test_note_persisted = _try_write_note(
                    adapter,
                    test_path,
                    test_markdown,
                    warnings,
                    f"update test note after question {question.id}",
                )

    completed_at = datetime.now() if now is None else created_at
    test_markdown = finalize_test_markdown(test_markdown, questions, grades, completed_at)
    if not _try_write_note(adapter, test_path, test_markdown, warnings, "finalize test note"):
        test_note_persisted = False

    entry = build_test_history_entry(filename, questions, grades, completed_at)
    history_updated = _try_write_note(adapter, history_path, update_history_markdown(history_markdown, entry), warnings, "update test history")

    score = sum(grade.points for grade in grades)
    output_func(f"Score: {score:g}/{len(questions)}")
    return VocabTestSessionResult(
        test_path=test_path if test_note_persisted else None,
        history_path=history_path,
        score=score,
        total=len(questions),
        warnings=warnings,
        pending_test_markdown="" if test_note_persisted else test_markdown,
        pending_history_entry="" if history_updated else entry,
        test_note_persisted=test_note_persisted,
        history_updated=history_updated,
    )


def load_recent_source_notes_from_adapter(
    adapter: ObsidianVaultAdapter,
    news_dir: str,
    limit: int = 20,
    warnings: list[str] | None = None,
) -> list[SourceNote]:
    news_dir = _normalize_dir(news_dir)
    refs = [
        ref
        for ref in adapter.list_notes(news_dir, recursive=True)
        if _is_source_note(news_dir, ref.path)
    ]
    refs.sort(key=lambda ref: (ref.modified, ref.path), reverse=True)

    notes: list[SourceNote] = []
    for ref in refs[:limit]:
        try:
            content = adapter.read_note(ref.path)
        except VaultReadError as exc:
            if warnings is not None:
                warnings.append(f"Could not read source note {ref.path}; skipping it: {exc}")
            continue
        if content is None:
            continue
        filename = PurePosixPath(ref.path).relative_to(PurePosixPath(news_dir)).as_posix()
        notes.append(SourceNote(filename=filename, content=content))
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
    completed_value = completed_at.strftime("%Y-%m-%d %H:%M")
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

    review_block = _review_needed_block(markdown, questions, grades)
    if "## Review Needed\n" in markdown:
        before, _sep, _after = markdown.partition("## Review Needed\n")
        markdown = before + "## Review Needed\n" + review_block + "\n"
    return markdown


def _review_needed_block(
    markdown: str,
    questions: Sequence[VocabQuestion],
    grades: Sequence[GradeResult],
) -> str:
    rows: list[str] = []
    for question, grade in zip(questions, grades, strict=False):
        if grade.result == "correct":
            continue
        user_answer = _recorded_answer(markdown, question.id)
        rows.extend(
            [
                f"### {question.candidate.term}",
                f"- source: [[{PurePosixPath(question.candidate.source_note).stem}]]",
                f"- prompt: {question.prompt}",
                f"- my_answer: {user_answer or '-'}",
                f"- correct_answer: {question.correct_answer}",
                f"- result: {grade.result}",
                f"- feedback: {grade.feedback}",
                f"- rationale: {grade.rationale or '-'}",
                "",
            ]
        )
    if not rows:
        return "- "
    return "\n".join(rows).rstrip()


def _recorded_answer(markdown: str, question_id: int) -> str:
    pattern = re.compile(
        rf"### {question_id}\. .*?\n- id:.*?\n.*?\n- user_answer:\s*(.*?)\n- result:",
        re.DOTALL,
    )
    match = pattern.search(markdown)
    if not match:
        return ""
    return " ".join(match.group(1).split())


def _question_batches(questions: Sequence[VocabQuestion], batch_size: int) -> list[list[VocabQuestion]]:
    size = max(1, batch_size)
    return [list(questions[index : index + size]) for index in range(0, len(questions), size)]


def _try_write_note(
    adapter: ObsidianVaultAdapter,
    note_path: str,
    content: str,
    warnings: list[str],
    operation: str,
) -> bool:
    try:
        adapter.write_note(note_path, content)
        return True
    except VaultWriteError as exc:
        warnings.append(f"Could not {operation}; keeping generated content in memory: {exc}")
        return False


def _is_source_note(news_dir: str, note_path: str) -> bool:
    try:
        relative = PurePosixPath(note_path).relative_to(PurePosixPath(news_dir))
    except ValueError:
        return False
    return "Test" not in relative.parts


def _normalize_dir(path: str) -> str:
    return PurePosixPath(path).as_posix().strip("/")


def _join_vault_path(*parts: str) -> str:
    clean_parts = [part.strip("/") for part in parts if part.strip("/")]
    return PurePosixPath(*clean_parts).as_posix()
