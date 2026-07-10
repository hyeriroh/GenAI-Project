from __future__ import annotations

import trafilatura


class ExtractionError(RuntimeError):
    pass


def extract_article_text(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ExtractionError("Could not download the article URL.")

    text = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not text or len(text.strip()) < 200:
        raise ExtractionError(
            "Could not extract enough article text. Please paste the article manually."
        )
    return text.strip()
