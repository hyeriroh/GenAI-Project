from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from english_news_agent.config import load_config
from english_news_agent.mcp_adapter import StdioMcpConfig, StdioMcpObsidianAdapter
from english_news_agent.models import AppConfig
from english_news_agent.obsidian_adapter import FileSystemObsidianAdapter
from english_news_agent.test_agent import SourceNote
from english_news_agent.test_orchestrator import finalize_test_markdown, run_vocab_test_session

InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run an English News vocabulary test from local Obsidian notes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Create and run a vocabulary test.")
    start.add_argument("--config", default="config.yaml", help="Path to config.yaml. config.local.yaml is preferred automatically.")
    start.add_argument("--limit", type=int, default=20, help="Number of questions to generate.")
    start.add_argument("--source-limit", type=int, default=20, help="Number of recent article notes to scan.")
    start.add_argument("--no-llm", action="store_true", help="Use deterministic fallback grading instead of the LLM judge.")
    start.add_argument("--adapter", choices=["local", "mcp"], default="local", help="Vault adapter to use.")

    args = parser.parse_args(argv)
    if args.command == "start":
        config = load_config(args.config)
        test_path = run_vocab_test(
            config=config,
            limit=args.limit,
            source_limit=args.source_limit,
            use_llm=not args.no_llm,
            adapter_name=args.adapter,
        )
        print(f"Saved test: {test_path}")


def run_vocab_test(
    config: AppConfig,
    limit: int = 20,
    source_limit: int = 20,
    use_llm: bool = True,
    input_func: InputFunc = input,
    output_func: OutputFunc = print,
    now: datetime | None = None,
    adapter_name: str = "local",
) -> Path:
    adapter = build_adapter(config, adapter_name)
    try:
        result = run_vocab_test_session(
            adapter=adapter,
            news_dir=config.obsidian.news_dir,
            study_settings=config.study,
            limit=limit,
            source_limit=source_limit,
            use_llm=use_llm,
            input_func=input_func,
            output_func=output_func,
            now=now,
        )
    finally:
        close = getattr(adapter, "close", None)
        if close:
            close()
    for warning in result.warnings:
        output_func(f"Warning: {warning}")
    if result.pending_history_entry:
        output_func(f"Pending history row: {result.pending_history_entry}")
    if result.test_path is None:
        output_func("Warning: test note was not persisted; generated markdown is available in session result.")
        return Path(config.obsidian.vault_path).expanduser() / config.obsidian.news_dir / "Test"
    if adapter_name == "mcp":
        return Path(result.test_path)
    return Path(config.obsidian.vault_path).expanduser() / Path(*Path(result.test_path).parts)


def build_adapter(config: AppConfig, adapter_name: str):
    if adapter_name == "local":
        return FileSystemObsidianAdapter(config.obsidian.vault_path)
    if adapter_name == "mcp":
        if config.mcp is None:
            raise RuntimeError("mcp config is required when --adapter mcp is used.")
        return StdioMcpObsidianAdapter(
            StdioMcpConfig(
                command=config.mcp.command,
                args=config.mcp.args,
                vault=config.mcp.vault,
                timeout_seconds=config.mcp.timeout_seconds,
            )
        )
    raise ValueError(f"Unknown adapter: {adapter_name}")


def news_directory(config: AppConfig) -> Path:
    return Path(config.obsidian.vault_path).expanduser() / config.obsidian.news_dir


def load_recent_source_notes(news_dir: Path, limit: int = 20) -> list[SourceNote]:
    if not news_dir.exists():
        return []

    note_paths = [
        path
        for path in news_dir.rglob("*.md")
        if "Test" not in path.relative_to(news_dir).parts
    ]
    note_paths.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)

    notes: list[SourceNote] = []
    for path in note_paths[:limit]:
        relative_name = path.relative_to(news_dir).as_posix()
        notes.append(SourceNote(filename=relative_name, content=path.read_text(encoding="utf-8")))
    return notes


if __name__ == "__main__":
    main()
