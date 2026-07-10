# English News Test Agent Protocol

This protocol defines how an AI assistant should run vocabulary tests with the
Obsidian MCP server. The Streamlit app remains focused on generating article
study notes. The conversational AI plus MCP handles review, testing, grading,
and history updates.

When the user asks for a vocabulary test in Codex/chat, do not only generate a
static worksheet. Enter live quiz mode: create the test note, present questions
in batches of 5 in the chat, wait for the user's answers, grade each submitted
answer immediately, update the same test note after each graded answer, then
finalize the result and update the history note.

The runtime path is adapter-based: `run_vocab_test_session()` receives an
`ObsidianVaultAdapter`, so the same workflow can run against a local vault, a
stdio MCP client, or the in-memory MCP mock adapter used by tests.

A local file-based runner is also available for end-to-end testing without MCP:

```bash
PYTHONPATH=src python -m english_news_agent.test_cli start --limit 20
```

## Trigger

Start this workflow when the user asks any equivalent of:

- "영어뉴스 단어시험 시작"
- "옵시디언 기반 단어시험 시작해"
- "영어 뉴스 단어 시험 봐줘"
- "옵시디언으로 단어 시험 봐줘"
- "최근 기사 기반으로 단어 퀴즈 내줘"
- "시험 결과 기록해줘"
- "방금 본 단어시험 저장해줘"

## Short Command Confirmation

When the user only says a short start command like `옵시디언 기반 단어시험 시작해`, ask this confirmation before creating files or asking questions:

`시험 출제부터 내 답변, 정답, 채점 결과를 실시간으로 같은 Test md에 업데이트하고, 마지막에 아래 오답노트까지 정리하는 방식으로 할까요?`

If the user answers yes, proceed with the live Test-folder workflow. If the user already included those requirements explicitly, skip this confirmation and proceed.

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
is the single long-term history file used for later personalization. Do not
create a `Quizzes` folder for this workflow.

## Chat Mode Contract

For a request like `영어뉴스 단어시험 시작`, the assistant should behave as the
test proctor in the conversation:

- Use `40 Resources/English News/Test/` as the canonical test folder; create it first if it does not exist.
- Never use `40 Resources/English News/Quizzes/` for this workflow.
- Use `test-history.md` as the canonical cumulative history file.
- Select about 20 questions from existing English News notes plus prior misses in history.
- Present questions in batches of 5 in chat and wait for answers to that batch.
- Grade each submitted answer immediately and briefly. If the user answers one question at a time, grade and update one at a time.
- Update the in-progress test note after every graded answer when MCP/file writes are available.
- At the end, finalize the same test note with score, answers, feedback, and review terms.
- Append the session summary to `test-history.md` so future tests can lightly personalize selection.
- Do not create a separate database, a separate result file, or a static-only worksheet.

## MCP Workflow

The implemented orchestrator is `run_vocab_test_session()` in
`src/english_news_agent/test_orchestrator.py`. It uses the adapter methods
`list_notes`, `read_note`, `ensure_folder`, and `write_note`.
`MockObsidianAdapter` verifies failure recovery in tests, and
`StdioMcpObsidianAdapter` calls `obsidian-mcp-kr` tools over stdio.

1. List or confirm the available vault.
2. Ensure `40 Resources/English News/Test` exists; create it if missing before writing any note.
3. Read `40 Resources/English News/Test/test-history.md`.
4. If the history note does not exist, create it with the default history
   template from `update_history_markdown("", entry)`.
5. Search recent notes under `40 Resources/English News`, excluding `Test`.
6. Read selected source notes.
7. Pass note contents and history markdown to `select_vocab_candidates()`.
8. Build a test filename with `test_filename()`.
9. Build the test body with `build_vocab_test_markdown()`.
10. Create the test note in `40 Resources/English News/Test`.
11. Show the next batch of up to 5 questions in chat and wait for the user's answers before continuing.
12. For each submitted answer:
    - Grade with `grade_answer()`.
    - Update the test markdown with `apply_answer_to_test_markdown()`.
    - Replace the Obsidian test note with the updated content.
13. At the end:
    - Finalize the same test note as completed; do not leave it `in_progress`.
    - Compute the score from `GradeResult.points`.
    - Write all questions, user answers, results, feedback, and rationale into that note.
    - Add a summary entry with `build_test_history_entry()`.
    - Update `test-history.md` with `update_history_markdown()`.
    - Only then tell the user the test is finished.

## Final Result Note Requirements

The assistant must not end the session with only chat feedback. A completed test
must be persisted as one Markdown note under `40 Resources/English News/Test/`.
The note is the official result record.

The final test note must include:

- frontmatter with `type: english_news_vocab_test`, `status: completed`,
  `created`, `completed`, `score`, and `total`
- source notes used for question selection
- selection policy summary
- every question, prompt, correct answer, user answer, result, feedback, and rationale
- result summary with score, correct, partial, incorrect, and completed timestamp
- detailed 오답노트 for every answer that was not fully correct, including prompt, my answer, correct answer, feedback, and rationale

If the quiz was already conducted in chat but the note was not written, rebuild
this completed note from the chat transcript and create it before replying that
the task is done. The next action after the final grade must be a write attempt
to the test note and history note, not a conversational summary. After that,
update `test-history.md` with the session summary. If a write requires
permission, ask for it and continue. If either write fails, keep the generated
Markdown in the response and state that it was not persisted.

## Result Recovery Mode

Use this mode when the user says the quiz was completed in chat but no Markdown
record was saved, for example `시험 결과 기록해줘` or `방금 본 단어시험 저장해줘`.

Do not generate new questions in recovery mode. Reconstruct the result from the
chat transcript and persist it.

Required recovery behavior:

1. Extract the already asked questions and the user's submitted answers from the chat.
2. Reuse the grades already given in chat. If grades are missing, grade the answers now.
3. Build a completed test note with `build_vocab_test_markdown()` shape where possible,
   then fill `user_answer`, `result`, `feedback`, and `rationale` for every answered question.
4. Ensure `40 Resources/English News/Test/` exists, then write the completed note to `40 Resources/English News/Test/YYYY-MM-DD_HHMM_vocab-test.md`.
5. Append the session summary to `40 Resources/English News/Test/test-history.md`.
6. If some question, answer, or grade cannot be recovered from chat, ask for only that missing data.
7. If MCP/file writing fails, provide the full pending Markdown and pending history row.

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
- Do not create static quiz-only notes under `Quizzes`; use live chat plus `Test`.
- Do not overwrite article notes during tests.
