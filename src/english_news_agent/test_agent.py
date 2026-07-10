from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from textwrap import dedent
from typing import Iterable, Sequence

from dotenv import load_dotenv
from openai import OpenAI

from english_news_agent.models import StudySettings
from english_news_agent.utils import slugify


class QuestionType(StrEnum):
    MEANING = "meaning"
    REVERSE = "reverse"
    FILL_BLANK = "fill_blank"


@dataclass(frozen=True)
class SourceNote:
    filename: str
    content: str


@dataclass(frozen=True)
class VocabCandidate:
    term: str
    meaning_ko: str
    source_note: str
    source_section: str
    part_of_speech: str = ""
    example_sentence: str = ""
    missed_count: int = 0
    correct_count: int = 0
    score: float = 0
    frequency_count: int = 1
    difficulty_score: int = 0
    importance_score: int = 0
    correct_streak: int = 0
    last_seen: str = ""


@dataclass(frozen=True)
class VocabQuestion:
    id: int
    candidate: VocabCandidate
    question_type: QuestionType
    prompt: str
    correct_answer: str


@dataclass(frozen=True)
class GradeResult:
    result: str
    feedback: str
    points: float
    rationale: str = ""


def select_vocab_candidates(
    notes: Sequence[SourceNote | dict[str, str]],
    history_markdown: str = "",
    limit: int = 10,
    today: date | None = None,
) -> list[VocabCandidate]:
    """Select review candidates from article notes and test history.

    Notes are expected newest-first. The scoring combines weak-history signals,
    recency, term frequency, difficulty, and source-section importance.
    """
    today = today or date.today()
    history = _parse_history(history_markdown)
    occurrences: list[tuple[int, VocabCandidate]] = []
    frequency: dict[str, int] = {}

    for note_index, note in enumerate(notes):
        source = _coerce_note(note)
        for candidate in extract_vocab_candidates(source):
            key = _key(candidate.term)
            occurrences.append((note_index, candidate))
            frequency[key] = frequency.get(key, 0) + 1

    deduped: dict[str, VocabCandidate] = {}
    for note_index, candidate in occurrences:
        key = _key(candidate.term)
        missed = history["missed"].get(key, 0)
        correct_streak = history["correct_streak"].get(key, 0)
        last_seen = history["last_seen"].get(key, "")
        frequency_count = frequency.get(key, 1)
        difficulty_score = _difficulty_score(candidate)
        importance_score = history["importance"].get(key, _importance_score(candidate))
        recency_bonus = max(0, 20 - note_index * 2)
        source_bonus = _source_section_bonus(candidate.source_section)
        frequency_bonus = min(frequency_count - 1, 4) * 2
        last_seen_adjustment = _last_seen_adjustment(last_seen, today)
        score = (
            recency_bonus
            + source_bonus
            + missed * 12
            - correct_streak * 5
            + frequency_bonus
            + difficulty_score
            + importance_score
            + last_seen_adjustment
        )
        scored = VocabCandidate(
            term=candidate.term,
            meaning_ko=candidate.meaning_ko,
            source_note=candidate.source_note,
            source_section=candidate.source_section,
            part_of_speech=candidate.part_of_speech,
            example_sentence=candidate.example_sentence,
            missed_count=missed,
            correct_count=correct_streak,
            score=score,
            frequency_count=frequency_count,
            difficulty_score=difficulty_score,
            importance_score=importance_score,
            correct_streak=correct_streak,
            last_seen=last_seen,
        )
        existing = deduped.get(key)
        if existing is None or scored.score > existing.score:
            deduped[key] = scored

    return sorted(
        deduped.values(),
        key=lambda item: (-item.score, -item.missed_count, -item.frequency_count, item.term.lower()),
    )[:limit]


def extract_vocab_candidates(note: SourceNote) -> list[VocabCandidate]:
    candidates: list[VocabCandidate] = []
    candidates.extend(_extract_vocabulary_table(note))
    candidates.extend(_extract_collocation_table(note))
    candidates.extend(_extract_useful_expressions(note))
    return candidates


def build_vocab_questions(candidates: Sequence[VocabCandidate]) -> list[VocabQuestion]:
    questions: list[VocabQuestion] = []
    question_cycle = [
        QuestionType.MEANING,
        QuestionType.FILL_BLANK,
        QuestionType.REVERSE,
    ]
    for index, candidate in enumerate(candidates, start=1):
        question_type = question_cycle[(index - 1) % len(question_cycle)]
        prompt, correct_answer = _question_prompt(candidate, question_type)
        questions.append(
            VocabQuestion(
                id=index,
                candidate=candidate,
                question_type=question_type,
                prompt=prompt,
                correct_answer=correct_answer,
            )
        )
    return questions


def build_vocab_test_markdown(
    candidates: Sequence[VocabCandidate],
    created_at: datetime | None = None,
) -> str:
    created_at = created_at or datetime.now()
    questions = build_vocab_questions(candidates)
    source_notes = sorted({question.candidate.source_note for question in questions})
    total = len(questions)

    lines = [
        "---",
        "type: english_news_vocab_test",
        "status: in_progress",
        f"created: {created_at.strftime('%Y-%m-%d %H:%M')}",
        "completed:",
        "score:",
        f"total: {total}",
        "tags:",
        "  - english",
        "  - news",
        "  - test",
        "---",
        "",
        f"# Vocabulary Test - {created_at.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Source Notes",
        *_source_note_lines(source_notes),
        "",
        "## Selection Policy",
        "- Prior incorrect answers and stale words are prioritized.",
        "- Recent English News notes are mixed with weak vocabulary.",
        "- Repeated article terms, difficult words, and important source sections receive small bonuses.",
        "- Words recently answered correctly several times are penalized.",
        "",
        "## Questions",
        "",
    ]

    for question in questions:
        lines.extend(
            [
                f"### {question.id}. {question.candidate.term}",
                f"- id: {question.id}",
                f"- type: {question.question_type.value}",
                f"- source: [[{_note_title(question.candidate.source_note)}]]",
                f"- prompt: {question.prompt}",
                f"- correct_answer: {question.correct_answer}",
                "- user_answer:",
                "- result:",
                "- feedback:",
                "- rationale:",
                "",
            ]
        )

    lines.extend(
        [
            "## Result Summary",
            "- score:",
            "- correct:",
            "- partial:",
            "- incorrect:",
            "- completed:",
            "",
            "## Review Needed",
            "",
        ]
    )
    return "\n".join(lines)


def grade_answer(
    question: VocabQuestion | dict,
    user_answer: str,
    settings: StudySettings | None = None,
    use_llm: bool = True,
) -> GradeResult:
    question = _coerce_question(question)
    answer = user_answer.strip()
    if not answer:
        return GradeResult("incorrect", "No answer was provided.", 0, "The learner submitted an empty answer.")

    if use_llm:
        try:
            return grade_answer_with_llm(question, answer, settings)
        except Exception:
            return grade_answer_with_rules(question, answer)

    return grade_answer_with_rules(question, answer)


def grade_answer_with_llm(
    question: VocabQuestion,
    user_answer: str,
    settings: StudySettings | None = None,
) -> GradeResult:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Create .env from .env.example.")

    settings = settings or StudySettings()
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=settings.model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strict but fair English vocabulary test grader for Korean learners. "
                    "Return only strict JSON matching the requested schema."
                ),
            },
            {"role": "user", "content": _build_grading_prompt(question, user_answer)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    raw_output = response.choices[0].message.content or ""
    return parse_grade_json(raw_output)


def grade_answer_with_rules(question: VocabQuestion | dict, user_answer: str) -> GradeResult:
    question = _coerce_question(question)
    answer = user_answer.strip()
    if not answer:
        return GradeResult("incorrect", "No answer was provided.", 0, "The learner submitted an empty answer.")

    if question.question_type in {QuestionType.REVERSE, QuestionType.FILL_BLANK}:
        if _key(answer) == _key(question.correct_answer):
            return GradeResult("correct", "Correct.", 1, "The submitted English expression exactly matches the expected answer.")
        if _key(answer) in _key(question.correct_answer) or _key(question.correct_answer) in _key(answer):
            return GradeResult(
                "partial",
                f"Close. The expected answer is '{question.correct_answer}'.",
                0.5,
                "The submitted expression partially overlaps with the expected answer.",
            )
        return GradeResult(
            "incorrect",
            f"The expected answer is '{question.correct_answer}'.",
            0,
            "The submitted English expression does not match the expected answer.",
        )

    overlap = _meaning_overlap(answer, question.correct_answer)
    if overlap >= 0.7:
        return GradeResult("correct", "Correct.", 1, "The Korean answer covers the expected meaning.")
    if overlap > 0:
        return GradeResult(
            "partial",
            f"Partially correct. A better answer is: {question.correct_answer}",
            0.5,
            "The Korean answer overlaps with the expected meaning but is incomplete.",
        )
    return GradeResult(
        "incorrect",
        f"A better answer is: {question.correct_answer}",
        0,
        "The Korean answer does not cover the expected meaning.",
    )


def parse_grade_json(raw_output: str) -> GradeResult:
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM grade response was not valid JSON.") from exc

    result = str(data.get("result", "")).strip().lower()
    if result not in {"correct", "partial", "incorrect"}:
        raise ValueError(f"Invalid grade result: {result}")

    if result == "correct":
        points = 1
    elif result == "partial":
        points = 0.5
    else:
        points = 0

    feedback = str(data.get("feedback", "")).strip() or "No feedback provided."
    rationale = str(data.get("rationale", "")).strip() or "No rationale provided."
    return GradeResult(result=result, feedback=feedback, points=points, rationale=rationale)


def _build_grading_prompt(question: VocabQuestion, user_answer: str) -> str:
    return dedent(
        f"""
        Grade briefly. Return only JSON.

        type: {question.question_type.value}
        target: {question.candidate.term}
        expected: {question.correct_answer}
        example: {question.candidate.example_sentence or ""}
        answer: {user_answer}

        JSON keys: result, points, feedback, rationale.
        result: correct | partial | incorrect.
        points: 1 | 0.5 | 0.
        feedback: one short sentence.
        rationale: one short sentence.

        Rules: accept Korean synonyms for meaning questions if context is preserved.
        For English answers, require the target expression or a clear inflected equivalent.
        Use partial only for close but incomplete answers.
        """
    ).strip()


def apply_answer_to_test_markdown(
    markdown: str,
    question_id: int,
    user_answer: str,
    grade: GradeResult,
) -> str:
    pattern = re.compile(
        rf"(### {question_id}\. .*?"
        rf"- user_answer:).*?"
        rf"(\n- result:).*?"
        rf"(\n- feedback:).*?"
        rf"(\n- rationale:).*?"
        rf"(?=\n\n### |\n\n## Result Summary|\Z)",
        re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        return (
            f"{match.group(1)} {_inline(user_answer)}"
            f"{match.group(2)} {grade.result}"
            f"{match.group(3)} {_inline(grade.feedback)}"
            f"{match.group(4)} {_inline(grade.rationale)}"
        )

    updated, count = pattern.subn(replace, markdown, count=1)
    if count == 0:
        raise ValueError(f"Question {question_id} was not found in the test markdown.")
    return updated


def build_test_history_entry(
    test_filename: str,
    questions: Sequence[VocabQuestion],
    grades: Sequence[GradeResult],
    completed_at: datetime | None = None,
) -> str:
    completed_at = completed_at or datetime.now()
    total = len(questions)
    score = sum(grade.points for grade in grades)
    review_terms = [
        question.candidate.term
        for question, grade in zip(questions, grades, strict=False)
        if grade.result != "correct"
    ]
    focus = "recent articles + prior misses"
    return (
        f"| {completed_at.strftime('%Y-%m-%d')} | [[{_note_title(test_filename)}]] | "
        f"{score:g} | {total} | {focus} | {', '.join(review_terms) or '-'} |"
    )


def update_history_markdown(history_markdown: str, entry: str) -> str:
    if not history_markdown.strip():
        return "\n".join(
            [
                "# English News Vocabulary Test History",
                "",
                "## Summary",
                "",
                "| Date | Test | Score | Total | Focus | Review Needed |",
                "| --- | --- | ---: | ---: | --- | --- |",
                entry,
                "",
                "## Weak Vocabulary",
                "",
                "| Word | Missed | Correct Streak | Last Seen | Importance | Notes |",
                "| --- | ---: | ---: | --- | ---: | --- |",
                "",
            ]
        )

    marker = "| --- | --- | ---: | ---: | --- | --- |"
    if marker in history_markdown:
        return history_markdown.replace(marker, f"{marker}\n{entry}", 1)
    return history_markdown.rstrip() + "\n" + entry + "\n"


def test_filename(created_at: datetime | None = None) -> str:
    created_at = created_at or datetime.now()
    return f"{created_at.strftime('%Y-%m-%d_%H%M')}_vocab-test.md"


def _extract_vocabulary_table(note: SourceNote) -> list[VocabCandidate]:
    rows = _table_rows(_section(note.content, "Vocabulary"))
    candidates: list[VocabCandidate] = []
    for row in rows:
        if len(row) < 4 or row[0].lower() == "word":
            continue
        candidates.append(
            VocabCandidate(
                term=row[0],
                part_of_speech=row[1],
                meaning_ko=row[2],
                example_sentence=row[3],
                source_note=note.filename,
                source_section="Vocabulary",
            )
        )
    return candidates


def _extract_collocation_table(note: SourceNote) -> list[VocabCandidate]:
    rows = _table_rows(_section(note.content, "Phrases and Collocations"))
    candidates: list[VocabCandidate] = []
    for row in rows:
        if len(row) < 3 or row[0].lower() == "phrase":
            continue
        candidates.append(
            VocabCandidate(
                term=row[0],
                meaning_ko=row[1],
                example_sentence=row[2],
                source_note=note.filename,
                source_section="Phrases and Collocations",
            )
        )
    return candidates


def _extract_useful_expressions(note: SourceNote) -> list[VocabCandidate]:
    section = _section(note.content, "Useful Expressions")
    candidates: list[VocabCandidate] = []
    pattern = re.compile(r"- \*\*(?P<term>.+?)\*\*:\s*(?P<meaning>.+?)(?:\n\s*Example:\s*(?P<example>.+))?(?=\n- |\Z)", re.DOTALL)
    for match in pattern.finditer(section):
        candidates.append(
            VocabCandidate(
                term=_clean_cell(match.group("term")),
                meaning_ko=_clean_cell(match.group("meaning")),
                example_sentence=_clean_cell(match.group("example") or ""),
                source_note=note.filename,
                source_section="Useful Expressions",
            )
        )
    return candidates


def _section(content: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(content)
    if not match:
        return ""
    next_heading = re.search(r"^## .+$", content[match.end() :], re.MULTILINE)
    if not next_heading:
        return content[match.end() :]
    return content[match.end() : match.end() + next_heading.start()]


def _table_rows(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [_clean_cell(cell) for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def _parse_history(history_markdown: str) -> dict[str, dict[str, int] | dict[str, str]]:
    missed: dict[str, int] = {}
    correct_streak: dict[str, int] = {}
    last_seen: dict[str, str] = {}
    importance: dict[str, int] = {}

    weak_rows = _table_rows(_section(history_markdown, "Weak Vocabulary"))
    if weak_rows:
        headers = [_history_header(cell) for cell in weak_rows[0]]
        for row in weak_rows[1:]:
            if not row or row[0].lower() == "word":
                continue
            values = {headers[index]: row[index] for index in range(min(len(headers), len(row)))}
            word = values.get("word") or row[0]
            key = _key(word)
            if not key:
                continue
            missed[key] = _to_int(values.get("missed", "0"))
            correct_streak[key] = _to_int(
                values.get("correct_streak", values.get("correct", values.get("streak", "0")))
            )
            last_seen_value = values.get("last_seen", "")
            if last_seen_value:
                last_seen[key] = last_seen_value
            if "importance" in values:
                importance[key] = _to_int(values["importance"])

    summary_rows = _table_rows(_section(history_markdown, "Summary"))
    if summary_rows:
        headers = [_history_header(cell) for cell in summary_rows[0]]
        for row in summary_rows[1:]:
            values = {headers[index]: row[index] for index in range(min(len(headers), len(row)))}
            completed_date = values.get("date", "")
            for term in _split_review_terms(values.get("review_needed", "")):
                key = _key(term)
                if not key:
                    continue
                missed[key] = max(1, missed.get(key, 0))
                if completed_date and key not in last_seen:
                    last_seen[key] = completed_date

    for word in re.findall(r"Result:\s*Correct\s*\n.*?(?:Word|Expression):\s*(.+)", history_markdown, re.IGNORECASE):
        key = _key(word)
        correct_streak[key] = correct_streak.get(key, 0) + 1

    return {
        "missed": missed,
        "correct_streak": correct_streak,
        "last_seen": last_seen,
        "importance": importance,
    }


def _question_prompt(candidate: VocabCandidate, question_type: QuestionType) -> tuple[str, str]:
    if question_type == QuestionType.REVERSE:
        return f"Write the English word or phrase for this Korean meaning: {candidate.meaning_ko}", candidate.term
    if question_type == QuestionType.FILL_BLANK:
        if candidate.example_sentence and candidate.term.lower() in candidate.example_sentence.lower():
            prompt = re.sub(re.escape(candidate.term), "____", candidate.example_sentence, count=1, flags=re.IGNORECASE)
        else:
            prompt = f"Fill in the blank with the article expression: ____ means {candidate.meaning_ko}."
        return prompt, candidate.term
    return f"What does '{candidate.term}' mean in this article context?", candidate.meaning_ko


def _meaning_overlap(answer: str, correct_answer: str) -> float:
    answer_tokens = _meaning_tokens(answer)
    correct_tokens = _meaning_tokens(correct_answer)
    if not answer_tokens or not correct_tokens:
        return 0
    return len(answer_tokens & correct_tokens) / len(correct_tokens)


def _meaning_tokens(value: str) -> set[str]:
    normalized = re.sub(r"[^\w가-힣]+", " ", value.lower())
    return {token for token in normalized.split() if len(token) > 1}


def _source_section_bonus(section: str) -> int:
    if section == "Vocabulary":
        return 6
    if section == "Useful Expressions":
        return 4
    return 2


def _difficulty_score(candidate: VocabCandidate) -> int:
    term = candidate.term.strip()
    token_count = len(term.split())
    length_bonus = 0
    if len(term) >= 12:
        length_bonus = 3
    elif len(term) >= 8:
        length_bonus = 2
    elif len(term) >= 6:
        length_bonus = 1
    phrase_bonus = min(max(token_count - 1, 0) * 2, 4)
    advanced_pos_bonus = 1 if candidate.part_of_speech.lower() in {"adjective", "adverb", "verb"} else 0
    return min(length_bonus + phrase_bonus + advanced_pos_bonus, 8)


def _importance_score(candidate: VocabCandidate) -> int:
    section_score = {
        "Vocabulary": 4,
        "Useful Expressions": 3,
        "Phrases and Collocations": 2,
    }.get(candidate.source_section, 1)
    example_bonus = 1 if candidate.example_sentence else 0
    phrase_bonus = 1 if len(candidate.term.split()) > 1 else 0
    return min(section_score + example_bonus + phrase_bonus, 6)


def _last_seen_adjustment(last_seen: str, today: date) -> int:
    seen_date = _parse_date(last_seen)
    if seen_date is None:
        return 4
    days = (today - seen_date).days
    if days < 0:
        return 0
    if days <= 2:
        return -8
    if days <= 7:
        return -4
    if days <= 21:
        return 2
    return 6


def _parse_date(value: str) -> date | None:
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(0), "%Y-%m-%d").date()
    except ValueError:
        return None


def _history_header(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    aliases = {
        "review_needed": "review_needed",
        "last_seen": "last_seen",
        "correct_streak": "correct_streak",
        "correct_count": "correct_streak",
        "streak": "correct_streak",
    }
    return aliases.get(normalized, normalized)


def _split_review_terms(value: str) -> list[str]:
    if not value or value.strip() == "-":
        return []
    return [term.strip() for term in value.split(",") if term.strip() and term.strip() != "-"]


def _source_note_lines(source_notes: Iterable[str]) -> list[str]:
    notes = list(source_notes)
    if not notes:
        return ["- "]
    return [f"- [[{_note_title(note)}]]" for note in notes]


def _note_title(filename: str) -> str:
    return filename.removesuffix(".md")


def _coerce_note(note: SourceNote | dict[str, str]) -> SourceNote:
    if isinstance(note, SourceNote):
        return note
    return SourceNote(filename=note["filename"], content=note["content"])


def _coerce_question(question: VocabQuestion | dict) -> VocabQuestion:
    if isinstance(question, VocabQuestion):
        return question
    candidate = question["candidate"]
    if not isinstance(candidate, VocabCandidate):
        candidate = VocabCandidate(**candidate)
    return VocabQuestion(
        id=question["id"],
        candidate=candidate,
        question_type=QuestionType(question["question_type"]),
        prompt=question["prompt"],
        correct_answer=question["correct_answer"],
    )


def _clean_cell(value: str) -> str:
    return value.replace("\\|", "|").replace("<br>", " ").strip()


def _key(value: str) -> str:
    return slugify(value, max_length=120)


def _inline(value: str) -> str:
    return value.replace("\n", " ").strip()


def _to_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0
