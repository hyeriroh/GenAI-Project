# English News Agent

English News Agent is a local Streamlit app for studying English newspaper articles. You can paste an article, extract one from a URL, or choose from RSS recommendations. The app analyzes the article with the OpenAI API and writes one Obsidian-compatible Markdown note per article.

This MVP is intended for local personal use. It does not use paid news APIs and does not store secrets in the repository.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Then set your API key:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

`.env` is ignored by git.

## Config

Edit `config.yaml` before generating notes:

```yaml
timezone: Asia/Seoul

obsidian:
  vault_path: ./obsidian-vault
  news_dir: English News
  vocab_dir: Vocabulary
```

Use `vault_path` for your local Obsidian vault. The app creates `news_dir` and `vocab_dir` if they do not exist. RSS feeds are also configured in `config.yaml`.

## Obsidian MCP Vocabulary Tests

The Streamlit app only generates article study notes. Vocabulary tests are run by an AI assistant through an Obsidian MCP server connected to the same vault. Set up the MCP server before asking the assistant to start a test.

Expected vault layout:

```text
<vault_path>/<news_dir>/
  Test/
    test-history.md
    YYYY-MM-DD_HHMM_vocab-test.md
```

When you ask `영어뉴스 단어시험 시작`, the assistant should use MCP to read recent English News notes, select vocabulary from existing note sections, create a test note under `Test`, grade answers one by one, update the test note after each answer, and append the final result to `test-history.md`.

The fixed operating protocol and fallback policy are documented in `docs/test-agent.md`. The pure selection, test rendering, grading, and history update logic lives in `src/english_news_agent/test_agent.py`.

## Streamlit App

```bash
./run
```

`./run` is a thin wrapper around `streamlit run app.py`.

The app has three modes:

- `Recommend Article`: default tab. Loads RSS links and automatically extracts the selected article into a read-only preview area. Extraction is rule-based; paragraph restructuring happens only when you generate the note.
- `Paste Article`: paste only a title and article body.
- `Article URL`: extract article text from a URL with `trafilatura`.

Each mode includes a lookup panel below `Generate` for word lookup and sentence/expression explanation. After a note is generated, lookups are appended to that article note.

If URL extraction fails, paste the article manually in the first tab.

## CLI

Dry run, which prints Markdown instead of writing files:

```bash
python main.py --input inputs/sample_article.md --title "Sample Article" --dry-run
```

Write files to your configured Obsidian vault:

```bash
python main.py --input inputs/sample_article.md --title "Sample Article"
```

## Output Files

The app writes one note:

```text
<vault_path>/<news_dir>/YYYY-MM-DD_slug.md
```

If a file already exists, a numeric suffix is appended instead of overwriting it.

In the Streamlit UI, each `Generate` button has a save directory field above it. Leave it blank to use the local default:

```text
./obsidian-vault/English News
```

Custom save directories are remembered in local UI history and can be deleted from the selector.

The article note includes frontmatter, the LLM-reconstructed original article paragraphs, paragraph-by-paragraph Korean translations, English and Korean summaries, key points, useful expressions, vocabulary and collocation tables, an expression lookup log, and reading notes.

## Tests

```bash
pytest
```
