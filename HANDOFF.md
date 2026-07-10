# English News Agent Handoff

Last updated: 2026-07-10 Asia/Seoul

## Project

- Workspace root: `/Users/hrroh/projects/my-agent`
- App root: `/Users/hrroh/projects/my-agent/english-news-agent`
- Real Obsidian vault: `/Users/hrroh/projects/obsidian`
- Local default note output: `/Users/hrroh/projects/my-agent/english-news-agent/obsidian-vault/English News`
- Streamlit entrypoint: `english-news-agent/app.py`
- CLI entrypoint: `english-news-agent/main.py`

## Current Goal

The app is a local Streamlit-based English newspaper study agent. It lets the user choose an RSS-recommended article, paste article text, or extract from a URL, then calls the OpenAI API and writes one Obsidian-compatible Markdown note per article.

The user now wants the agent's job to stay focused on generating Markdown study notes. The earlier vocabulary quiz generator idea was rolled back. Obsidian knowledge access is intended to happen through MCP instead.

## How To Run

From the workspace root:

```bash
cd /Users/hrroh/projects/my-agent
./run
```

From the app root:

```bash
cd /Users/hrroh/projects/my-agent/english-news-agent
./run
```

Both wrappers ultimately run:

```bash
streamlit run app.py
```

If `streamlit` is missing, install dependencies:

```bash
cd /Users/hrroh/projects/my-agent/english-news-agent
python -m pip install -r requirements.txt
```

## Important Files

- `/Users/hrroh/projects/my-agent/run`
  - Root wrapper so the user can run the app with `./run` from `/Users/hrroh/projects/my-agent`.
- `/Users/hrroh/projects/my-agent/english-news-agent/run`
  - App wrapper around `streamlit run app.py`.
- `/Users/hrroh/projects/my-agent/english-news-agent/app.py`
  - Main Streamlit UI.
- `/Users/hrroh/projects/my-agent/english-news-agent/src/english_news_agent/analyzer.py`
  - OpenAI calls, article analysis, paragraph structure retry/fallback, expression lookup.
- `/Users/hrroh/projects/my-agent/english-news-agent/src/english_news_agent/renderer.py`
  - Markdown rendering.
- `/Users/hrroh/projects/my-agent/english-news-agent/src/english_news_agent/writer.py`
  - Note path construction, file writing, expression lookup appending.
- `/Users/hrroh/projects/my-agent/english-news-agent/config.yaml`
  - Config currently points to the real Obsidian vault.
- `/Users/hrroh/projects/my-agent/english-news-agent/.save_dir_history.json`
  - Created at runtime. Stores recent output directories for the Streamlit save directory field. Ignored by git.

## Current Config

`english-news-agent/config.yaml` currently uses:

```yaml
obsidian:
  vault_path: /Users/hrroh/projects/obsidian
  news_dir: 40 Resources/English News
  vocab_dir: 40 Resources/Vocabulary
```

However, the Streamlit UI has a save directory input directly above each Generate button.

- If the user leaves the field blank, Streamlit saves to the original local default:
  `/Users/hrroh/projects/my-agent/english-news-agent/obsidian-vault/English News`
- If the user enters an absolute directory, that directory is used.
- If the user enters a relative directory, it is resolved against:
  `/Users/hrroh/projects/my-agent/english-news-agent`
- Non-empty successful save directories are added to history.
- History entries can be selected, used, and deleted from the UI.

## Streamlit UI State

The UI uses a radio selector rather than separate Streamlit tabs:

- `Recommend Article`
- `Paste Article`
- `Article URL`

Current behavior:

- `Recommend Article` is the default.
- Selecting a recommended article automatically extracts the article.
- The recommended article view shows:
  - article selector
  - source URL
  - extracted article preview
  - save directory control
  - Generate button
  - lookup panel below Generate
- There should be no extra title/body input fields under the recommended article Generate button.
- `Paste Article` only has title and body fields.
- `Article URL` only has URL extraction flow plus preview.
- Each mode has an expression lookup panel below Generate, not a separate tab.

After Generate:

- The app writes one Markdown article note.
- The UI shows the saved note path.
- `Korean Summary` appears in a collapsed expander.
- `Full Korean Translation` appears in a collapsed expander.
- Full translation in the UI follows the generated article paragraph breaks.
- The full translation is not added as a separate note section.

## Article Structure Behavior

The user does not want raw extracted text saved directly as `Original Article`.

Desired behavior:

- URL/RSS extraction stays rule-based with `trafilatura`.
- The LLM reads the article and reconstructs meaning-based paragraphs.
- The LLM must preserve original sentence order and wording.
- It may only decide paragraph boundaries.
- The Markdown note's `Original Article` section should use the LLM-reconstructed paragraph grouping.
- `단락별 Translation` should use the same reconstructed paragraphs and attach Korean translation paragraph by paragraph.

Fallback behavior:

- `analyzer.py` tries paragraph restructuring up to 2 times.
- If both attempts look sentence-by-sentence, it no longer hard-fails.
- It marks `analysis.structure_type = "sentence"` and returns the result.
- Renderer then uses `문장별 Translation` and `Sentence N` labels instead of paragraph labels.
- The user explicitly asked not to show a scary error in this case; fallback to sentence output after two attempts is acceptable.

## Expression Lookup Behavior

Each mode includes lookup below Generate.

Word lookup UI should show:

- Natural Korean
- Part of Speech
- English Definition
- Roots / Origin
- Nuance / Context
- Synonyms
- Antonyms
- Examples

Word lookup note logging:

- Do not append the full web explanation.
- Append only a concise row to the existing `## Vocabulary` table format.

Sentence lookup UI should show:

- Korean translation first
- Syntax explanation
- Grammar points
- Difficult words

Sentence lookup should not show `Natural Korean`.

Sentence lookup note logging:

- Append detailed explanation to `## Expression Lookup Log`.

## Markdown Output

The app now writes one note per article, not separate article and vocabulary notes for new UI generation.

Note sections include:

- YAML frontmatter
- Title
- Source URL when available
- Original Article using LLM paragraph grouping
- Korean summary
- English summary
- Key points
- Useful expressions
- Vocabulary table
- Phrases and Collocations
- Reading Notes
- Expression Lookup Log

Older local files may still include prior split vocabulary-note output in `english-news-agent/obsidian-vault/Vocabulary`; those are historical artifacts.

## Obsidian / MCP Work

The user asked to connect AI with Obsidian via MCP instead of building quiz features inside this app.

Set up completed:

- Cloned `obsidian-mcp-kr` to:
  `/Users/hrroh/projects/my-agent/tools/obsidian-mcp-kr`
- Built it with npm.
- Registered Codex MCP server:
  - name: `obsidian-mcp-kr`
  - command: `node`
  - args:
    `/Users/hrroh/projects/my-agent/tools/obsidian-mcp-kr/build/main.js /Users/hrroh/projects/obsidian`
- `codex mcp list` showed it as enabled in the previous session.

Important caveat:

- The current Codex session may not dynamically expose newly registered MCP tools.
- If MCP tools are missing, restart Codex or open a new Codex session.

Existing generated notes were copied to:

- `/Users/hrroh/projects/obsidian/40 Resources/English News`
- `/Users/hrroh/projects/obsidian/40 Resources/Vocabulary`

## Rolled Back

Vocabulary quiz generation was started and then removed at the user's request.

Deleted/removed concepts:

- `src/english_news_agent/quiz.py`
- `tests/test_quiz.py`
- `Vocabulary Quiz` UI mode
- README quiz documentation

Recent search had no active `quiz`, `Vocabulary Quiz`, `load_vocabulary`, `grade_quiz`, or `write_quiz` references.

## Validation

Latest test run:

```bash
cd /Users/hrroh/projects/my-agent/english-news-agent
pytest
```

Result:

```text
13 passed in 0.28s
```

Also previously validated:

```bash
python -m py_compile app.py main.py src/english_news_agent/*.py src/english_news_agent/extractors/*.py src/english_news_agent/sources/*.py
```

Result: passed.

## Git / Worktree State

Current `git status --short` from `/Users/hrroh/projects/my-agent`:

```text
?? english-news-agent/
?? run
?? tools/
```

This means the project directory, root `run` wrapper, and MCP tool clone are untracked. Do not assume there are commits to revert to.

Do not commit secrets. `english-news-agent/.env` exists locally and contains the user's OpenAI key. It must remain ignored.

## User Preferences / Notes

- User prefers concise Korean explanations.
- User wants token usage kept low when possible.
- User strongly prefers simple, maintainable code.
- UI should avoid extra input fields.
- Recommended Article should be the initial/default workflow.
- Article extraction should be automatic once an article is selected.
- Generated article notes should preserve article content while allowing the LLM to regroup paragraphs by meaning.
- The app's responsibility should remain Markdown generation; deeper Obsidian knowledge usage should happen through MCP.

## Recent Last Change

The user asked to make execution possible via `./run`.

Implemented:

- Added `/Users/hrroh/projects/my-agent/english-news-agent/run`
- Added `/Users/hrroh/projects/my-agent/run`
- Updated `english-news-agent/README.md` to show `./run`
- Verified:
  - `bash -n run`
  - executable permissions
  - `pytest` passing
