from __future__ import annotations

from pydantic import BaseModel, Field


class UsefulExpression(BaseModel):
    expression: str
    meaning_ko: str
    example_sentence: str


class VocabularyItem(BaseModel):
    word: str
    part_of_speech: str = ""
    meaning_ko: str
    example_sentence: str


class CollocationItem(BaseModel):
    phrase: str
    meaning_ko: str
    example_sentence: str


class SentenceTranslation(BaseModel):
    original: str
    korean_translation: str


class ParagraphTranslation(BaseModel):
    original: str
    korean_translation: str
    sentences: list[SentenceTranslation] = Field(default_factory=list)


class ArticleAnalysis(BaseModel):
    title: str
    structure_type: str = "paragraph"
    paragraph_translations: list[ParagraphTranslation] = Field(default_factory=list)
    korean_translation: str
    english_summary: str
    korean_summary: str
    key_points: list[str] = Field(default_factory=list)
    useful_expressions: list[UsefulExpression] = Field(default_factory=list)
    vocabulary: list[VocabularyItem] = Field(default_factory=list)
    collocations: list[CollocationItem] = Field(default_factory=list)


class ExpressionLookup(BaseModel):
    expression: str
    lookup_type: str = "sentence"
    explanation_ko: str
    natural_translation_ko: str
    sentence_translation_ko: str = ""
    part_of_speech: str = ""
    etymology_or_roots: str = ""
    english_definition: str = ""
    synonyms: list[str] = Field(default_factory=list)
    antonyms: list[str] = Field(default_factory=list)
    syntax_notes: list[str] = Field(default_factory=list)
    grammar_notes: list[str] = Field(default_factory=list)
    difficult_words: list[str] = Field(default_factory=list)
    example_sentences: list[str] = Field(default_factory=list)


class RssFeed(BaseModel):
    name: str
    url: str


class RecommendedArticle(BaseModel):
    title: str
    source: str
    link: str
    published: str = ""


class ObsidianConfig(BaseModel):
    vault_path: str
    news_dir: str
    vocab_dir: str


class StudySettings(BaseModel):
    model: str = "gpt-4.1-mini"
    max_vocabulary: int = 20
    max_expressions: int = 10
    target_language: str = "Korean"


class McpConfig(BaseModel):
    command: str = "node"
    args: list[str] = Field(default_factory=list)
    vault: str = ""
    timeout_seconds: float = 10


class AppConfig(BaseModel):
    timezone: str = "Asia/Seoul"
    obsidian: ObsidianConfig
    study: StudySettings = Field(default_factory=StudySettings)
    mcp: McpConfig | None = None
    rss_feeds: list[RssFeed] = Field(default_factory=list)
