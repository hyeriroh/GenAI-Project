# English News Test Agent Protocol

This protocol defines how an AI assistant should run vocabulary tests with the
Obsidian MCP server. The Streamlit app remains focused on generating article
study notes. The conversational AI plus MCP handles review, testing, grading,
and history updates.

When the user asks for a vocabulary test in Codex/chat, do not only generate a
static worksheet. Enter live quiz mode: create the test note, ask one question
at a time in the chat, grade each answer immediately, update the same test note
after each answer, then finalize the result and update the history note.

The runtime path is adapter-based: `run_vocab_test_session()` receives an
`ObsidianVaultAdapter`, so the same workflow can run against a local vault, a
future stdio MCP client, or the in-memory MCP mock adapter used by tests.

A local file-based runner is also available for end-to-end testing without MCP:

```bash
PYTHONPATH=src python -m english_news_agent.test_cli start --limit 10
```

## Trigger

Start this workflow when the user asks any equivalent of:

- "영어뉴스 단어시험 시작"
- "영어 뉴스 단어 시험 봐줘"
- "최근 기사 기반으로 단어 퀴즈 내줘"

## Obsidian Layout

Use this folder under the connected vault:

```text
40 Resources/English News/
  Test/
    test-history.md
    YYYY-MM-DD_HHMM_vocab-test.md
```

If the user has configured a different English News folder, use that path
instead. Keep test files and results in the same test note. `test-history.md`
is the single long-term history file used for later personalization.

## Chat Mode Contract

For a request like `영어뉴스 단어시험 시작`, the assistant should behave as the
test proctor in the conversation:

- Use `40 Resources/English News/Test/` as the canonical test folder.
- Use `test-history.md` as the canonical cumulative history file.
- Select questions from existing English News notes plus prior misses in history.
- Ask exactly one question at a time in chat and wait for the user's answer.
- Grade the answer immediately and briefly.
- Update the in-progress test note after every answer when MCP/file writes are available.
- At the end, finalize the same test note with score, answers, feedback, and review terms.
- Append the session summary to `test-history.md` so future tests can lightly personalize selection.
- Do not create a separate database or a separate result file.

## MCP Workflow

The implemented orchestrator is `run_vocab_test_session()` in
`src/english_news_agent/test_orchestrator.py`. It uses the adapter methods
`list_notes`, `read_note`, `ensure_folder`, and `write_note`.
`MockObsidianAdapter` verifies failure recovery in tests, and
`StdioMcpObsidianAdapter` calls `obsidian-mcp-kr` tools over stdio.

1. List or confirm the available vault.
2. Ensure `40 Resources/English News/Test` exists.
3. Read `40 Resources/English News/Test/test-history.md`.
4. If the history note does not exist, create it with the default history
   template from `update_history_markdown("", entry)`.
5. Search recent notes under `40 Resources/English News`, excluding `Test`.
6. Read selected source notes.
7. Pass note contents and history markdown to `select_vocab_candidates()`.
8. Build a test filename with `test_filename()`.
9. Build the test body with `build_vocab_test_markdown()`.
10. Create the test note in `40 Resources/English News/Test`.
11. Ask one question at a time in chat and wait for the user's answer before continuing.
12. For each user answer:
    - Grade with `grade_answer()`.
    - Update the test markdown with `apply_answer_to_test_markdown()`.
    - Replace the Obsidian test note with the updated content.
13. At the end:
    - Compute the score from `GradeResult.points`.
    - Add a summary entry with `build_test_history_entry()`.
    - Update `test-history.md` with `update_history_markdown()`.

## Candidate Selection Policy

`select_vocab_candidates()` is deterministic and should receive source notes
newest-first.

Priority order:

1. Words or expressions missed in `test-history.md`.
2. Words not tested recently, based on `Last Seen`.
3. Vocabulary from recent English News article notes.
4. Useful expressions from recent article notes.
5. Phrases and collocations from recent article notes.

Scoring:

- Prior missed words receive a large bonus.
- Recent source notes receive a recency bonus.
- Words not tested recently receive a small spaced-review bonus; words tested in the last few days are penalized.
- Repeated terms across article notes receive a frequency bonus.
- Longer terms, multi-word expressions, and advanced parts of speech receive a difficulty bonus.
- Vocabulary and useful-expression sections receive source-importance bonuses, with optional `Importance` values from `test-history.md` taking priority.
- Words with a higher `Correct Streak` are penalized.

## Question Types

Use a rotating mix:

- `meaning`: English word or phrase -> Korean meaning.
- `fill_blank`: article example sentence with the target removed.
- `reverse`: Korean meaning -> English word or phrase.

## Grading Policy

Use `grade_answer()` for concise LLM-judge grading. The judge returns `result`, `points`, `feedback`, and `rationale`; keep feedback and rationale to one short sentence each. If the LLM judge is unavailable or returns invalid JSON, the code falls back to deterministic rule-based grading.

- `correct`: full credit.
- `partial`: half credit, close but incomplete.
- `incorrect`: no credit.

For Korean meaning answers, the LLM judge may accept natural synonyms that preserve the article-context meaning. For English fill-blank or reverse questions, it should require the target expression or a clearly equivalent inflected form.

## Timeout And Fallback Policy

MCP failures should not silently corrupt test history.

- Vault listing timeout:
  - Ask the user to confirm the vault name.
  - If already known from prior context, continue with that vault.
- `Test` folder creation failure:
  - Stop before creating a test.
  - Report the path that failed.
- `test-history.md` read failure:
  - Continue with an empty history.
  - Create or replace history only after the test completes.
- Recent article search failure:
  - Ask the user to provide one or more source note names.
  - Do not invent source notes.
- Test note create failure:
  - Continue the quiz in chat only if the user agrees.
  - At the end, provide the full Markdown for manual save or retry creation.
- Per-answer update failure:
  - Continue grading in chat.
  - Keep the in-memory test markdown.
  - Retry replacing the whole test note at the end.
- History update failure:
  - Do not rerun the test.
  - Provide the generated history row and ask whether to retry.

## Non-Goals

- Do not add this workflow to the Streamlit app unless explicitly requested.
- Do not create a separate database. Obsidian Markdown is the source of record.
- Do not overwrite article notes during tests.
