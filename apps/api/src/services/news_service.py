"""AstraOS Services — News Ingestion (RSS + GDELT, all free)."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class NewsItem:
    """A single news item."""
    def __init__(self, title: str, source: str, url: str, published: datetime,
                 summary: str = "", category: str = "general", sentiment: float = 0.0):
        self.title = title
        self.source = source
        self.url = url
        self.published = published
        self.summary = summary
        self.category = category
        self.sentiment = sentiment

    def to_dict(self) -> dict:
        return {
            "title": self.title, "source": self.source, "url": self.url,
            "published": self.published.isoformat(), "summary": self.summary,
            "category": self.category, "sentiment": self.sentiment,
        }


class NewsProvider(ABC):
    """Abstract news provider interface."""

    @abstractmethod
    async def fetch_news(self, query: str = "", limit: int = 20) -> list[NewsItem]: ...


class RSSGDELTProvider(NewsProvider):
    """FREE news provider using RSS feeds + GDELT API."""

    RSS_FEEDS = [
        ("https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "Economic Times"),
        ("https://www.moneycontrol.com/rss/marketreports.xml", "MoneyControl"),
        ("https://www.livemint.com/rss/markets", "LiveMint"),
    ]

    GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    async def fetch_news(self, query: str = "India stock market", limit: int = 20) -> list[NewsItem]:
        """Fetch news from RSS feeds and GDELT."""
        items: list[NewsItem] = []

        # GDELT (structured, free, global coverage)
        try:
            gdelt_items = await self._fetch_gdelt(query, limit=limit // 2)
            items.extend(gdelt_items)
        except Exception as e:
            logger.warning("GDELT fetch failed", error=str(e))

        # RSS feeds
        for feed_url, source in self.RSS_FEEDS:
            try:
                rss_items = await self._fetch_rss(feed_url, source, limit=limit // 4)
                items.extend(rss_items)
            except Exception as e:
                logger.warning("RSS fetch failed", source=source, error=str(e))

        # Sort by time, limit
        items.sort(key=lambda x: x.published, reverse=True)
        return items[:limit]

    async def _fetch_gdelt(self, query: str, limit: int = 10) -> list[NewsItem]:
        """Fetch from GDELT GDoc API (free, no key required)."""
        params = {
            "query": f"{query} sourcelang:eng",
            "mode": "artlist",
            "maxrecords": str(limit),
            "format": "json",
            "sort": "datedesc",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.GDELT_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items = []
        for article in data.get("articles", []):
            items.append(NewsItem(
                title=article.get("title", ""),
                source=article.get("domain", "GDELT"),
                url=article.get("url", ""),
                published=datetime.strptime(
                    article.get("seendate", "20260101T000000Z"), "%Y%m%dT%H%M%SZ"
                ).replace(tzinfo=timezone.utc),
                summary=article.get("title", ""),
                category="market",
            ))
        return items

    async def _fetch_rss(self, feed_url: str, source: str, limit: int = 5) -> list[NewsItem]:
        """Parse RSS XML feed (basic parser, no external lib needed)."""
        import xml.etree.ElementTree as ET

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(feed_url)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        items = []

        for item in root.iter("item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            desc = item.findtext("description", "")

            try:
                from email.utils import parsedate_to_datetime
                published = parsedate_to_datetime(pub_date).replace(tzinfo=timezone.utc)
            except Exception:
                published = datetime.now(timezone.utc)

            items.append(NewsItem(
                title=title, source=source, url=link,
                published=published, summary=desc[:200],
                category="market",
            ))

            if len(items) >= limit:
                break

        return items


def get_news_provider(provider: str = "rss_gdelt") -> NewsProvider:
    """Factory: get news provider by name."""
    providers = {"rss_gdelt": RSSGDELTProvider}
    return providers.get(provider, RSSGDELTProvider)()
