# English News Agent Instructions

This repository is an English News Agent for Obsidian-based English study.

## Vocabulary Test Trigger

When the user asks anything equivalent to:

- "옵시디언 기반 내 단어시험 만들어줘"
- "영어뉴스 단어시험 시작"
- "영어 뉴스 단어 시험 봐줘"
- "최근 기사 기반으로 단어 퀴즈 내줘"

read and follow `docs/test-agent.md` before acting.

Do not treat this as a request to merely generate a static worksheet. Enter live quiz mode in the chat.

## Required Test Behavior

For Obsidian-based vocabulary tests:

1. Use `40 Resources/English News/Test/` as the canonical test folder unless the user's config says otherwise.
2. Use `test-history.md` in that `Test/` folder as the cumulative history file.
3. Select questions from existing English News notes plus prior misses in `test-history.md`.
4. Create one test note named like `YYYY-MM-DD_HHMM_vocab-test.md`.
5. Ask exactly one question at a time in chat and wait for the user's answer.
6. Grade each answer immediately and briefly.
7. Update the same in-progress test note after every answer when MCP or file writes are available.
8. At the end, finalize the same test note with score, answers, feedback, rationale, and review terms.
9. Append the session summary to `test-history.md` so later tests can lightly personalize selection.
10. Do not create a separate database or a separate result file.

## Implementation Pointers

- Core protocol: `docs/test-agent.md`
- Test generation/grading/history logic: `src/english_news_agent/test_agent.py`
- Test orchestrator: `src/english_news_agent/test_orchestrator.py`
- Obsidian adapters: `src/english_news_agent/obsidian_adapter.py`, `src/english_news_agent/mcp_adapter.py`
- Local/MCP CLI runner: `PYTHONPATH=src python -m english_news_agent.test_cli start --limit 10`
- MCP CLI runner: `PYTHONPATH=src python -m english_news_agent.test_cli start --adapter mcp --limit 10`

Prefer MCP tools connected to the user's real Obsidian vault when available. If MCP is unavailable, use the local configured vault path or explain the missing requirement clearly.
