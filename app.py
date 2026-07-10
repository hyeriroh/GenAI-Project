from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from english_news_agent.analyzer import (
    AnalysisParseError,
    ParagraphStructureError,
    analyze_article,
    explain_expression,
)
from english_news_agent.config import load_config
from english_news_agent.extractors.url_extractor import ExtractionError, extract_article_text
from english_news_agent.sources.rss import fetch_recommended_articles
from english_news_agent.writer import append_expression_lookup, write_notes


st.set_page_config(page_title="English News Agent", page_icon="EN", layout="wide")

APP_ROOT = Path(__file__).resolve().parent
DEFAULT_UI_OUTPUT_DIR = APP_ROOT / "obsidian-vault" / "English News"
SAVE_DIR_HISTORY_PATH = APP_ROOT / ".save_dir_history.json"


@st.cache_data(show_spinner=False)
def get_config():
    return load_config("config.yaml")


@st.cache_data(show_spinner=False, ttl=900)
def get_recommendations():
    config = get_config()
    return fetch_recommended_articles(config.rss_feeds)


def generate_notes(
    title: str,
    article_text: str,
    source_url: str | None = None,
    output_dir: str | Path | None = None,
) -> Path | None:
    if not title.strip():
        st.error("Please enter a title.")
        return None
    if not article_text.strip():
        st.error("Please provide article text.")
        return None

    config = get_config()
    with st.spinner("Analyzing article with OpenAI..."):
        try:
            analysis = analyze_article(article_text, title, config.study)
        except AnalysisParseError as exc:
            st.error("OpenAI returned invalid JSON. Raw output is shown below for debugging.")
            st.code(exc.raw_output, language="json")
            return None
        except ParagraphStructureError as exc:
            st.error("OpenAI split the article sentence-by-sentence instead of grouping it by meaning. Raw output is shown below.")
            st.code(exc.raw_output, language="json")
            return None
        except Exception as exc:
            st.error(str(exc))
            return None

    article_path = write_notes(analysis, article_text, config, source_url, output_dir)
    st.session_state["active_note_path"] = str(article_path)
    st.session_state["active_article_text"] = article_text
    st.session_state["active_article_title"] = analysis.title
    st.success("Notes saved.")
    st.write(f"Article note: `{article_path}`")
    if analysis.structure_type == "sentence":
        st.warning("The model could not create meaning-based paragraphs after two tries, so this note was saved with sentence-based translation sections.")
    with st.expander("Korean Summary", expanded=False):
        st.write(analysis.korean_summary)
    with st.expander("Full Korean Translation", expanded=False):
        render_full_korean_translation(analysis)
    return article_path


def clear_legacy_preview_state() -> None:
    for key in ["recommended_preview", "url_preview", "recommended_title", "url_title"]:
        st.session_state.pop(key, None)


def load_save_dir_history() -> list[str]:
    if not SAVE_DIR_HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(SAVE_DIR_HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, str) and item.strip()]


def save_save_dir_history(history: list[str]) -> None:
    SAVE_DIR_HISTORY_PATH.write_text(
        json.dumps(history[:20], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_save_dir_history(directory: str) -> None:
    directory = directory.strip()
    if not directory:
        return
    history = [item for item in load_save_dir_history() if item != directory]
    save_save_dir_history([directory, *history])


def delete_save_dir_history(directory: str) -> None:
    save_save_dir_history([item for item in load_save_dir_history() if item != directory])


def resolve_output_dir(directory: str) -> Path:
    if not directory.strip():
        return DEFAULT_UI_OUTPUT_DIR
    path = Path(directory).expanduser()
    if not path.is_absolute():
        path = APP_ROOT / path
    return path


def output_directory_control(scope: str) -> tuple[Path, str]:
    st.caption(f"Save directory. Leave blank for `{DEFAULT_UI_OUTPUT_DIR}`")
    history = load_save_dir_history()
    selected = ""
    if history:
        selected = st.selectbox(
            "Recent save directories",
            ["", *history],
            key=f"{scope}_save_dir_history",
        )
        history_col, delete_col = st.columns([1, 1])
        with history_col:
            if st.button("Use selected", key=f"{scope}_use_save_dir", disabled=not selected):
                st.session_state[f"{scope}_save_dir"] = selected
                st.rerun()
        with delete_col:
            if st.button("Delete selected", key=f"{scope}_delete_save_dir", disabled=not selected):
                delete_save_dir_history(selected)
                st.rerun()

    directory = st.text_input(
        "Save directory",
        key=f"{scope}_save_dir",
        placeholder=str(DEFAULT_UI_OUTPUT_DIR),
    )
    return resolve_output_dir(directory), directory.strip()


def render_full_korean_translation(analysis) -> None:
    if analysis.paragraph_translations:
        for item in analysis.paragraph_translations:
            if item.korean_translation.strip():
                st.markdown(f"<p>{escape(item.korean_translation.strip())}</p>", unsafe_allow_html=True)
        return

    for paragraph in [item.strip() for item in analysis.korean_translation.split("\n\n") if item.strip()]:
        st.markdown(f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>", unsafe_allow_html=True)


def paste_article_tab() -> None:
    title = st.text_input("Title", key="paste_title")
    article_text = st.text_area("Article text", height=420, key="paste_article")
    output_dir, raw_output_dir = output_directory_control("paste")
    if st.button("Generate", key="paste_generate", type="primary"):
        if generate_notes(title, article_text, output_dir=output_dir):
            add_save_dir_history(raw_output_dir)
    lookup_panel("paste", article_text)


def render_article_preview(article_text: str) -> None:
    st.caption("Extracted article")
    for paragraph in [item.strip() for item in article_text.split("\n\n") if item.strip()]:
        st.markdown(f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>", unsafe_allow_html=True)


def article_url_tab() -> None:
    url = st.text_input("Article URL", key="url_input")
    if st.button("Extract", key="url_extract"):
        if not url.strip():
            st.error("Please enter an article URL.")
            return
        try:
            extracted_text = extract_article_text(url)
            st.session_state["url_article_text"] = extracted_text
            st.session_state["url_article_url"] = url
        except ExtractionError as exc:
            st.error(str(exc))

    article_text = st.session_state.get("url_article_text", "")
    if article_text:
        render_article_preview(article_text)
    output_dir, raw_output_dir = output_directory_control("url")
    if st.button("Generate", key="url_generate", type="primary"):
        if generate_notes(url, article_text, st.session_state.get("url_article_url", url), output_dir):
            add_save_dir_history(raw_output_dir)
    lookup_panel("url", article_text)


def recommended_articles_tab() -> None:
    try:
        articles = get_recommendations()
    except Exception as exc:
        st.error(f"Could not load RSS feeds: {exc}")
        return

    if not articles:
        st.info("No recommended articles found.")
        return

    labels = [
        f"{article.title} | {article.source} | {article.published or 'No date'}"
        for article in articles
    ]
    selected_index = st.selectbox("Select an article", range(len(labels)), format_func=labels.__getitem__)
    selected = articles[selected_index]
    selected_key = selected.link

    if st.session_state.get("recommended_selected_url") != selected_key:
        st.session_state["recommended_selected_url"] = selected_key
        st.session_state["recommended_article_title"] = selected.title
        st.session_state["recommended_title"] = selected.title
        st.session_state["recommended_article_url"] = selected.link
        with st.spinner("Extracting selected article..."):
            try:
                article_text = extract_article_text(selected.link)
                st.session_state["recommended_article_text"] = article_text
            except ExtractionError as exc:
                st.session_state["recommended_article_text"] = ""
                st.error(str(exc))

    article_text = st.session_state.get("recommended_article_text", "")
    st.write(st.session_state.get("recommended_article_url", selected.link))
    if article_text:
        render_article_preview(article_text)
    output_dir, raw_output_dir = output_directory_control("recommended")
    if st.button("Generate", key="recommended_generate", type="primary"):
        if generate_notes(
            selected.title,
            article_text,
            st.session_state.get("recommended_article_url", selected.link),
            output_dir,
        ):
            add_save_dir_history(raw_output_dir)
    lookup_panel("recommended", article_text)


def lookup_panel(scope: str, article_text: str) -> None:
    active_note_path = st.session_state.get("active_note_path", "")
    context = article_text or st.session_state.get("active_article_text", "")

    st.divider()
    st.subheader("Lookup")
    lookup_type = st.radio(
        "Lookup type",
        ["Word", "Sentence"],
        horizontal=True,
        key=f"{scope}_lookup_type",
    )
    query = st.text_area(
        "Word or sentence",
        key=f"{scope}_lookup_query",
        placeholder="Enter a word, phrase, or difficult sentence",
        height=90,
    )

    if st.button("Explain", key=f"{scope}_lookup_generate"):
        if not query.strip():
            st.error("Please enter a word or sentence.")
            return

        config = get_config()
        with st.spinner("Explaining..."):
            try:
                lookup = explain_expression(
                    query,
                    context,
                    config.study,
                    lookup_type=lookup_type.lower(),
                )
            except AnalysisParseError as exc:
                st.error("OpenAI returned invalid JSON. Raw output is shown below for debugging.")
                st.code(exc.raw_output, language="json")
                return
            except Exception as exc:
                st.error(str(exc))
                return

        render_lookup_result(lookup)

        if active_note_path:
            append_expression_lookup(active_note_path, lookup)
            if lookup.lookup_type == "word":
                st.success(f"Word added to the Vocabulary section in `{active_note_path}`")
            else:
                st.success(f"Lookup appended to `{active_note_path}`")
        else:
            st.warning("No active article note yet, so this lookup was not written to a file.")


def render_lookup_result(lookup) -> None:
    if lookup.lookup_type == "word":
        st.markdown(f"**Natural Korean:** {lookup.natural_translation_ko}")
        st.write(f"Part of Speech: {lookup.part_of_speech or '-'}")
        st.write(f"English Definition: {lookup.english_definition or '-'}")
        st.write(f"Roots / Origin: {lookup.etymology_or_roots or '-'}")
        st.markdown("**Nuance / Context**")
        st.write(lookup.explanation_ko)
        st.markdown("**Synonyms**")
        st.write(", ".join(lookup.synonyms) if lookup.synonyms else "-")
        st.markdown("**Antonyms**")
        st.write(", ".join(lookup.antonyms) if lookup.antonyms else "-")
        st.markdown("**Examples**")
        for sentence in lookup.example_sentences:
            st.write(f"- {sentence}")
        return

    st.markdown("**해석**")
    st.write(lookup.sentence_translation_ko or lookup.natural_translation_ko)
    st.markdown("**구문 설명**")
    for note in lookup.syntax_notes or [lookup.explanation_ko]:
        st.write(f"- {note}")
    st.markdown("**문법 포인트**")
    for note in lookup.grammar_notes:
        st.write(f"- {note}")
    st.markdown("**어려운 단어**")
    for word in lookup.difficult_words:
        st.write(f"- {word}")


def main() -> None:
    st.title("English News Agent")
    clear_legacy_preview_state()
    mode = st.radio(
        "Mode",
        ["Recommend Article", "Paste Article", "Article URL"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if mode == "Recommend Article":
        recommended_articles_tab()
    elif mode == "Paste Article":
        paste_article_tab()
    elif mode == "Article URL":
        article_url_tab()


if __name__ == "__main__":
    main()
