# English News Agent Instructions

This repository is an English News Agent for Obsidian-based English study.

## Vocabulary Test Trigger

When the user asks anything equivalent to:

- "옵시디언 기반 내 단어시험 만들어줘"
- "영어뉴스 단어시험 시작"
- "옵시디언 기반 단어시험 시작해"
- "영어 뉴스 단어 시험 봐줘"
- "옵시디언으로 단어 시험 봐줘"
- "최근 기사 기반으로 단어 퀴즈 내줘"
- "시험 결과 기록해줘"
- "방금 본 단어시험 저장해줘"

read and follow `docs/test-agent.md` before acting.

If the user gives only a short start command such as `옵시디언 기반 단어시험 시작해`, first confirm the intended live workflow in Korean:

`시험 출제부터 내 답변, 정답, 채점 결과를 실시간으로 같은 Test md에 업데이트하고, 마지막에 아래 오답노트까지 정리하는 방식으로 할까요?`

If the user agrees, run the workflow below. If the user already explicitly requested that full workflow, do not ask again.

Do not treat this as a request to merely generate a static worksheet. Enter live quiz mode in the chat. Never create only a finished quiz note and stop.

## Required Test Behavior

For Obsidian-based vocabulary tests:

1. Use `40 Resources/English News/Test/` as the canonical test folder unless the user's config says otherwise. If `Test/` does not exist under English News, create it before writing any test note.
2. Never create `40 Resources/English News/Quizzes/` for this workflow.
3. Use `test-history.md` in that `Test/` folder as the cumulative history file.
4. Select about 20 questions from existing English News notes plus prior misses in `test-history.md`.
5. Create one test note named like `YYYY-MM-DD_HHMM_vocab-test.md` before the quiz starts.
6. In chat, present questions in batches of 5. After each batch, wait for the user's answers before continuing.
7. Grade each submitted answer immediately and briefly. If the user answers one at a time, grade and update one at a time.
8. Update the same in-progress test note after every graded answer when MCP or file writes are available, so the note always contains the asked question, correct answer, user answer, grade, feedback, and rationale.
9. At the end, finalize the same test note with score, answers, feedback, rationale, and review terms.
10. Append the session summary to `test-history.md` so later tests can lightly personalize selection.
11. Do not create a separate database, a separate result file, or a static-only worksheet.

## Completion Gate

A vocabulary test is not complete until Obsidian has a completed Markdown result note under `40 Resources/English News/Test/`.

Before saying the test is finished, verify or write the test note with:

- every question that was asked
- the user's answer for each question
- result: `correct`, `partial`, or `incorrect`
- brief feedback and rationale for each answer
- final score, correct/partial/incorrect counts, completed timestamp, and a detailed 오답노트 with prompt, my answer, correct answer, feedback, and rationale

Then append the session row to `40 Resources/English News/Test/test-history.md`. After the final answer is graded, your next action must be an MCP/file write attempt, not a conversational wrap-up. If the live quiz happened before a note was created, reconstruct the completed test note from the chat transcript and create it immediately. If MCP/file writing requires permission, ask for that permission and continue after it is granted. If MCP/file writing fails, say clearly that the Markdown was not persisted and provide the pending test Markdown plus pending history row.

## Result Recovery Trigger

If the user says the quiz ended but was not saved, or asks to record the result after a live quiz, reconstruct the completed test note from the current chat transcript. Do not start a new quiz unless the user explicitly asks for a new one.

Recovery steps:

1. Identify the questions, correct answers if available, user answers, grades, feedback, and score from the chat.
2. If any required field is missing, ask only for the missing answers/grades needed to save the result.
3. Ensure `40 Resources/English News/Test/` exists; create it if missing.
4. Create or update one `YYYY-MM-DD_HHMM_vocab-test.md` result note with `status: completed`.
5. Append a summary row to `40 Resources/English News/Test/test-history.md`.
6. Only then tell the user the result was recorded.

## Implementation Pointers

- Core protocol: `docs/test-agent.md`
- Test generation/grading/history logic: `src/english_news_agent/test_agent.py`
- Test orchestrator: `src/english_news_agent/test_orchestrator.py`
- Obsidian adapters: `src/english_news_agent/obsidian_adapter.py`, `src/english_news_agent/mcp_adapter.py`
- Local/MCP CLI runner: `PYTHONPATH=src python -m english_news_agent.test_cli start --limit 20`
- MCP CLI runner: `PYTHONPATH=src python -m english_news_agent.test_cli start --adapter mcp --limit 20`

Prefer MCP tools connected to the user's real Obsidian vault when available. If MCP is unavailable, use the local configured vault path or explain the missing requirement clearly.
