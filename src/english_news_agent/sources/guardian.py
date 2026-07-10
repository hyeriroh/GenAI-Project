from __future__ import annotations

from english_news_agent.models import RssFeed
from english_news_agent.sources.rss import fetch_recommended_articles


GUARDIAN_WORLD_RSS = RssFeed(
    name="The Guardian World",
    url="https://www.theguardian.com/world/rss",
)


def fetch_guardian_world(limit_per_feed: int = 10):
    return fetch_recommended_articles([GUARDIAN_WORLD_RSS], limit_per_feed=limit_per_feed)

