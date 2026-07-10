from __future__ import annotations

import json
import os
import re
from textwrap import dedent

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from english_news_agent.models import ArticleAnalysis, ExpressionLookup, ParagraphTranslation, StudySettings


class AnalysisParseError(RuntimeError):
    def __init__(self, raw_output: str):
        super().__init__("OpenAI response was not valid analysis JSON.")
        self.raw_output = raw_output


class ParagraphStructureError(RuntimeError):
    def __init__(self, raw_output: str):
        super().__init__("The model kept splitting the article sentence-by-sentence instead of grouping by meaning.")
        self.raw_output = raw_output


def mark_sentence_fallback(analysis: ArticleAnalysis) -> ArticleAnalysis:
    analysis.structure_type = "sentence"
    return analysis


def build_sentence_fallback_analysis(
    analysis: ArticleAnalysis,
    article_text: str,
    sentence_translations: dict[str, str] | None = None,
) -> ArticleAnalysis:
    source_sentences = _split_sentences(article_text)
    exact_translations = _exact_sentence_translation_map(analysis)
    sentence_translations = sentence_translations or {}
    analysis.paragraph_translations = [
        ParagraphTranslation(
            original=sentence,
            korean_translation=sentence_translations.get(
                _normalize_sentence(sentence),
                exact_translations.get(_normalize_sentence(sentence), ""),
            ),
        )
        for sentence in source_sentences
    ]
    analysis.korean_translation = "\n\n".join(
        item.korean_translation for item in analysis.paragraph_translations if item.korean_translation
    )
    return mark_sentence_fallback(analysis)


def analyze_article(
    article_text: str,
    title: str,
    settings: StudySettings | None = None,
) -> ArticleAnalysis:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Create .env from .env.example.")

    settings = settings or StudySettings()
    client = OpenAI(api_key=api_key)

    fallback_analysis: ArticleAnalysis | None = None
    for attempt in range(2):
        prompt = _build_prompt(article_text, title, settings, retry_sentence_alignment=attempt > 0)
        response = client.chat.completions.create(
            model=settings.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an English newspaper study assistant. "
                        "Return only strict JSON matching the requested schema."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw_output = response.choices[0].message.content or ""
        analysis = parse_analysis_json(raw_output)
        fallback_analysis = analysis
        if article_sentences_match(article_text, analysis) and _is_sentence_by_sentence_analysis(article_text, analysis):
            analysis.structure_type = "sentence"
            return analysis

    if fallback_analysis is None:
        raise AnalysisParseError("")
    return build_sentence_fallback_analysis(
        fallback_analysis,
        article_text,
        _translate_sentences_for_fallback(client, article_text, title, settings),
    )


def explain_expression(
    expression: str,
    article_context: str = "",
    settings: StudySettings | None = None,
    lookup_type: str = "sentence",
) -> ExpressionLookup:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Create .env from .env.example.")

    settings = settings or StudySettings()
    client = OpenAI(api_key=api_key)
    prompt = _build_expression_prompt(expression, article_context, lookup_type)

    response = client.chat.completions.create(
        model=settings.model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You explain difficult English expressions for Korean learners. "
                    "Return only strict JSON matching the requested schema."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    raw_output = response.choices[0].message.content or ""
    return parse_expression_json(raw_output)


def parse_analysis_json(raw_output: str) -> ArticleAnalysis:
    try:
        data = json.loads(raw_output)
        analysis = ArticleAnalysis.model_validate(data)
        if not analysis.paragraph_translations:
            raise ValueError("paragraph_translations is required for note generation.")
        return analysis
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise AnalysisParseError(raw_output) from exc


def parse_expression_json(raw_output: str) -> ExpressionLookup:
    try:
        data = json.loads(raw_output)
        return ExpressionLookup.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AnalysisParseError(raw_output) from exc


def _build_prompt(
    article_text: str,
    title: str,
    settings: StudySettings,
    retry_sentence_alignment: bool = False,
) -> str:
    retry_instruction = ""
    if retry_sentence_alignment:
        retry_instruction = """
        Your previous sentence alignment was rejected. Try again with exactly one output item per source sentence, in the same order, preserving every original sentence exactly once.
        """

    return dedent(
        f"""
        Analyze this English newspaper article for a Korean learner of English.

        Title: {title}
        {retry_instruction}

        Return strict JSON with exactly these top-level keys:
        - title: string
        - paragraph_translations: array of objects with original, korean_translation
        - korean_translation: string
        - english_summary: string
        - korean_summary: string
        - key_points: array of strings
        - useful_expressions: array of objects with expression, meaning_ko, example_sentence
        - vocabulary: array of objects with word, part_of_speech, meaning_ko, example_sentence
        - collocations: array of objects with phrase, meaning_ko, example_sentence

        Limits:
        - vocabulary: up to {settings.max_vocabulary} high-value words
        - useful_expressions: up to {settings.max_expressions} expressions
        - collocations: up to {settings.max_expressions} phrases
        - Korean content should be natural Korean.
        - Example sentences should be short and practical.

        Sentence-by-sentence translation rules:
        - paragraph_translations is kept for schema compatibility, but it must contain sentence units, not paragraphs.
        - Split the article into source sentences. Each array item must contain exactly one original sentence and exactly one Korean translation.
        - paragraph_translations.original must preserve the original sentence wording exactly. Do not paraphrase, rewrite, omit, merge, or reorder sentences.
        - paragraph_translations.korean_translation must translate only that one source sentence. Do not include translations of earlier or later sentences.
        - Do not prefix translations with "해석:" or any label.
        - korean_translation should be the full article translation created by joining the same sentence translations in order.
        - The extracted text may have unreliable line breaks, including one sentence per line. Ignore those line breaks but preserve sentence order and wording.

        Article:
        {article_text}
        """
    ).strip()


def _looks_sentence_split(analysis: ArticleAnalysis) -> bool:
    paragraphs = [item.original.strip() for item in analysis.paragraph_translations if item.original.strip()]
    if len(paragraphs) <= 6:
        return False

    single_sentence_count = sum(1 for paragraph in paragraphs if _sentence_count(paragraph) <= 1)
    return len(paragraphs) > 12 or single_sentence_count / len(paragraphs) >= 0.6


def article_sentences_match(article_text: str, analysis: ArticleAnalysis) -> bool:
    source_sentences = [_normalize_sentence(sentence) for sentence in _split_sentences(article_text)]
    analysis_sentences = [
        _normalize_sentence(sentence)
        for item in analysis.paragraph_translations
        for sentence in _split_sentences(item.original)
    ]
    return bool(source_sentences) and source_sentences == analysis_sentences


def _is_sentence_by_sentence_analysis(article_text: str, analysis: ArticleAnalysis) -> bool:
    source_sentences = [_normalize_sentence(sentence) for sentence in _split_sentences(article_text)]
    items = [item for item in analysis.paragraph_translations if item.original.strip()]
    if len(items) != len(source_sentences):
        return False
    return all(
        _sentence_count(item.original) == 1
        and _normalize_sentence(item.original) == source_sentences[index]
        for index, item in enumerate(items)
    )


def _exact_sentence_translation_map(analysis: ArticleAnalysis) -> dict[str, str]:
    translations: dict[str, str] = {}
    for item in analysis.paragraph_translations:
        original = item.original.strip()
        translation = item.korean_translation.strip()
        if translation and _sentence_count(original) == 1:
            translations[_normalize_sentence(original)] = translation
    return translations


def _translate_sentences_for_fallback(
    client,
    article_text: str,
    title: str,
    settings: StudySettings,
) -> dict[str, str]:
    source_sentences = _split_sentences(article_text)
    if not source_sentences:
        return {}
    try:
        response = client.chat.completions.create(
            model=settings.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You translate English news sentences into concise Korean. "
                        "Return only strict JSON matching the requested schema."
                    ),
                },
                {"role": "user", "content": _build_sentence_fallback_prompt(source_sentences, title)},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw_output = response.choices[0].message.content or ""
        return _parse_sentence_fallback_translations(raw_output, source_sentences)
    except Exception:
        return {}


def _build_sentence_fallback_prompt(source_sentences: list[str], title: str) -> str:
    numbered_sentences = "\n".join(f"{index}. {sentence}" for index, sentence in enumerate(source_sentences, start=1))
    return dedent(
        f"""
        Translate each sentence into Korean for a news-reading study note.

        Title: {title}

        Return strict JSON with exactly one top-level key:
        - translations: array of objects with index, original, korean_translation

        Rules:
        - One input sentence must produce exactly one Korean translation.
        - korean_translation must translate only that sentence. Do not include other sentences.
        - Do not prefix translations with "해석:" or any label.
        - Keep Korean concise and natural.
        - Preserve each original sentence exactly as provided.
        - Keep the same order and index numbers.

        Sentences:
        {numbered_sentences}
        """
    ).strip()


def _parse_sentence_fallback_translations(raw_output: str, source_sentences: list[str]) -> dict[str, str]:
    data = json.loads(raw_output)
    rows = data.get("translations", [])
    if not isinstance(rows, list) or len(rows) != len(source_sentences):
        return {}
    translations: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            return {}
        original = str(row.get("original", "")).strip()
        expected = source_sentences[index]
        if _normalize_sentence(original) != _normalize_sentence(expected):
            return {}
        translation = str(row.get("korean_translation", "")).strip()
        if translation:
            translations[_normalize_sentence(expected)] = translation
    return translations


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+(?=[\"'‘’“”A-Z0-9])", normalized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _sentence_count(text: str) -> int:
    return len(_split_sentences(text))


def _normalize_sentence(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')


def _build_expression_prompt(expression: str, article_context: str, lookup_type: str = "sentence") -> str:
    focus = "a vocabulary word" if lookup_type == "word" else "an English expression or sentence"
    return dedent(
        f"""
        Explain this {focus} for a Korean learner.

        Query:
        {expression}

        Article context, if available:
        {article_context}

        Return strict JSON with exactly these top-level keys:
        - expression: string
        - lookup_type: string, either "word" or "sentence"
        - explanation_ko: string
        - natural_translation_ko: string
        - sentence_translation_ko: string
        - part_of_speech: string
        - etymology_or_roots: string
        - english_definition: string
        - synonyms: array of strings
        - antonyms: array of strings
        - syntax_notes: array of strings
        - grammar_notes: array of strings
        - difficult_words: array of strings
        - example_sentences: array of strings

        If this is a word lookup:
        - expression should be the word or phrase itself.
        - lookup_type must be "word".
        - explanation_ko should explain nuance and article-context meaning in Korean.
        - natural_translation_ko should be the best Korean meaning in this article context.
        - part_of_speech should include the English part of speech.
        - etymology_or_roots should explain useful roots, prefixes, suffixes, or word origin if helpful.
        - english_definition should be a concise learner-friendly English-English dictionary definition.
        - synonyms should include useful English synonyms.
        - antonyms should include useful English antonyms, or [] if none are natural.
        - example_sentences should include 3 practical English examples.

        If this is a sentence lookup:
        - lookup_type must be "sentence".
        - sentence_translation_ko should be a natural Korean translation of the full query.
        - explanation_ko should briefly explain the overall meaning in Korean.
        - syntax_notes should explain the sentence structure/chunks in Korean.
        - grammar_notes should explain key grammar points in Korean.
        - difficult_words should list difficult words or phrases with short Korean meanings, like "breach: 위반하다".
        - For fields that do not apply, use "" or [].
        """
    ).strip()
