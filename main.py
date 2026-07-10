from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from english_news_agent.analyzer import AnalysisParseError, analyze_article
from english_news_agent.config import load_config
from english_news_agent.renderer import render_article_note
from english_news_agent.writer import build_output_path, write_notes


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate English news study notes.")
    parser.add_argument("--input", required=True, help="Path to a text or Markdown article file.")
    parser.add_argument("--title", required=True, help="Article title.")
    parser.add_argument("--dry-run", action="store_true", help="Print Markdown instead of writing files.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml.")
    args = parser.parse_args()

    config = load_config(args.config)
    article_text = Path(args.input).read_text(encoding="utf-8")

    try:
        analysis = analyze_article(article_text=article_text, title=args.title, settings=config.study)
    except AnalysisParseError as exc:
        print("OpenAI returned invalid JSON. Raw output:")
        print(exc.raw_output)
        raise SystemExit(1) from exc

    if args.dry_run:
        article_path = build_output_path(analysis, config)
        print(render_article_note(analysis, article_text))
        print(f"\nWould write:\n- {article_path}")
        return

    article_path = write_notes(analysis, article_text, config)
    print(f"Wrote article note: {article_path}")


if __name__ == "__main__":
    main()
