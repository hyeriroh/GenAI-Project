from __future__ import annotations

import feedparser

from english_news_agent.models import RecommendedArticle, RssFeed


def fetch_recommended_articles(feeds: list[RssFeed], limit_per_feed: int = 5) -> list[RecommendedArticle]:
    articles: list[RecommendedArticle] = []
    for feed in feeds:
        parsed = feedparser.parse(feed.url)
        for entry in parsed.entries[:limit_per_feed]:
            articles.append(
                RecommendedArticle(
                    title=getattr(entry, "title", "Untitled"),
                    source=feed.name,
                    link=getattr(entry, "link", ""),
                    published=getattr(entry, "published", ""),
                )
            )
    return [article for article in articles if article.link]

