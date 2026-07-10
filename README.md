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

`config.yaml` is the shared default. For your own machine, create `config.local.yaml`; it is loaded before `config.yaml` and is ignored by git.

```yaml
timezone: Asia/Seoul

obsidian:
  vault_path: /path/to/your/obsidian-vault
  news_dir: 40 Resources/English News
  vocab_dir: 40 Resources/Vocabulary

mcp:
  command: node
  args:
    - /path/to/obsidian-mcp-kr/build/main.js
    - /path/to/your/obsidian-vault
  vault: your-vault-name
  timeout_seconds: 10
```

`vault_path` can be absolute, relative, or use `~`. The app creates `news_dir` and `vocab_dir` if they do not exist. RSS feeds stay in `config.yaml` unless you want to override them locally.

## Obsidian MCP Vocabulary Tests

Vocabulary tests use an Obsidian MCP server connected to the same vault. This project uses `jkf87/obsidian-mcp-kr` as the reference server.

Install the MCP server outside this repository:

```bash
git clone https://github.com/jkf87/obsidian-mcp-kr.git
cd obsidian-mcp-kr
npm install
npm run build
```

Register it with your AI assistant using this shape:

```json
{
  "mcpServers": {
    "obsidian-mcp-kr": {
      "command": "node",
      "args": [
        "/path/to/obsidian-mcp-kr/build/main.js",
        "/path/to/your/obsidian-vault"
      ]
    }
  }
}
```

After registration, restart the assistant if the MCP tools are not visible. Then ask `영어뉴스 단어시험 시작` or `옵시디언 기반 내 단어시험 만들어줘`. The root `AGENTS.md` routes those requests to the live quiz protocol. The intended flow is a live chat quiz: Codex asks one question at a time, grades each answer, updates the in-progress test note, and finalizes the result at the end. Test files are stored under:

```text
<vault_path>/<news_dir>/Test/
  test-history.md
  YYYY-MM-DD_HHMM_vocab-test.md
```

The detailed protocol is in `docs/test-agent.md`; the selection, LLM-judge grading, fallback grading, and history logic is in `src/english_news_agent/test_agent.py`. `test-history.md` is used on later tests for light personalization.

You can also run the local file-based test runner without MCP:

```bash
PYTHONPATH=src python -m english_news_agent.test_cli start --limit 10
```

To run through the stdio MCP adapter, add `mcp` settings to `config.local.yaml` and use:

```bash
PYTHONPATH=src python -m english_news_agent.test_cli start --adapter mcp --limit 10
```

Use `--no-llm` to grade with the deterministic fallback rules.

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
