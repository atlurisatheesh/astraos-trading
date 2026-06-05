"""AstraOS Services — Multi-Source Financial News Engine.

Dedicated, targeted scrapers and RSS parsers for top Indian finance portals:
- Economic Times (RSS feeds for Markets, Economy, sectors)
- LiveMint (breaking market news RSS)
- Moneycontrol (market reports RSS)
- GDELT (global structured news API)

Aggregator merges feeds, deduplicates, and tags symbols (e.g. "Reliance" → "RELIANCE.NS").
Structured output feeds directly into the FinBERT Sentiment agent.

All sources are free — no API keys required.
"""

import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256

import httpx
import structlog

from .news_service import NewsItem, NewsProvider

logger = structlog.get_logger()


# ── Symbol Tagging ──────────────────────────────────────────

# Common company name → NSE symbol mapping for Indian markets
_COMPANY_SYMBOL_MAP: dict[str, str] = {
    "reliance": "RELIANCE",
    "reliance industries": "RELIANCE",
    "tata consultancy": "TCS",
    "tcs": "TCS",
    "infosys": "INFY",
    "hdfc bank": "HDFCBANK",
    "hdfc": "HDFCBANK",
    "icici bank": "ICICIBANK",
    "icici": "ICICIBANK",
    "sbi": "SBIN",
    "state bank": "SBIN",
    "wipro": "WIPRO",
    "itc": "ITC",
    "larsen": "LT",
    "l&t": "LT",
    "hcl tech": "HCLTECH",
    "hcltech": "HCLTECH",
    "bharti airtel": "BHARTIARTL",
    "airtel": "BHARTIARTL",
    "axis bank": "AXISBANK",
    "kotak": "KOTAKBANK",
    "kotak mahindra": "KOTAKBANK",
    "maruti": "MARUTI",
    "maruti suzuki": "MARUTI",
    "bajaj finance": "BAJFINANCE",
    "bajaj finserv": "BAJFINSV",
    "sun pharma": "SUNPHARMA",
    "tata motors": "TATAMOTORS",
    "hindustan unilever": "HINDUNILVR",
    "hul": "HINDUNILVR",
    "tata steel": "TATASTEEL",
    "asian paints": "ASIANPAINT",
    "dr reddy": "DRREDDY",
    "ultratech": "ULTRACEMCO",
    "power grid": "POWERGRID",
    "ntpc": "NTPC",
    "tech mahindra": "TECHM",
    "adani enterprises": "ADANIENT",
    "adani": "ADANIENT",
    "jsw steel": "JSWSTEEL",
    "ongc": "ONGC",
    "nifty": "^NSEI",
    "sensex": "^BSESN",
    "bank nifty": "^NSEBANK",
    "banknifty": "^NSEBANK",
}

_SYMBOL_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(_COMPANY_SYMBOL_MAP, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def tag_symbols(text: str) -> list[str]:
    """Extract NSE symbols mentioned in a text string.

    Returns deduplicated list of NSE symbols found in the text.
    """
    matches = _SYMBOL_PATTERN.findall(text.lower())
    symbols = list(dict.fromkeys(_COMPANY_SYMBOL_MAP[m.lower()] for m in matches if m.lower() in _COMPANY_SYMBOL_MAP))
    return symbols


# ── Individual News Providers ───────────────────────────────


class EconomicTimesProvider(NewsProvider):
    """Economic Times RSS feed parser — Markets, Economy, and sector news."""

    FEEDS = [
        ("https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "ET Markets"),
        ("https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms", "ET Economy"),
        ("https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms", "ET Stocks"),
    ]

    async def fetch_news(self, query: str = "", limit: int = 20) -> list[NewsItem]:
        items: list[NewsItem] = []
        for feed_url, source in self.FEEDS:
            try:
                fetched = await self._parse_rss(feed_url, source, limit=limit // len(self.FEEDS) + 1)
                items.extend(fetched)
            except Exception as e:
                logger.warning("ET RSS fetch failed", source=source, error=str(e))
        return self._filter_by_query(items, query)[:limit]

    async def _parse_rss(self, feed_url: str, source: str, limit: int = 10) -> list[NewsItem]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(feed_url)
            resp.raise_for_status()

        return _parse_rss_xml(resp.text, source, limit)

    @staticmethod
    def _filter_by_query(items: list[NewsItem], query: str) -> list[NewsItem]:
        if not query:
            return items
        query_lower = query.lower()
        return [i for i in items if query_lower in i.title.lower() or query_lower in i.summary.lower()]


class LiveMintProvider(NewsProvider):
    """LiveMint RSS feed parser — breaking market news."""

    FEEDS = [
        ("https://www.livemint.com/rss/markets", "Mint Markets"),
        ("https://www.livemint.com/rss/money", "Mint Money"),
    ]

    async def fetch_news(self, query: str = "", limit: int = 20) -> list[NewsItem]:
        items: list[NewsItem] = []
        for feed_url, source in self.FEEDS:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(feed_url)
                    resp.raise_for_status()
                fetched = _parse_rss_xml(resp.text, source, limit=limit // len(self.FEEDS) + 1)
                items.extend(fetched)
            except Exception as e:
                logger.warning("Mint RSS fetch failed", source=source, error=str(e))
        return items[:limit]


class MoneycontrolProvider(NewsProvider):
    """Moneycontrol RSS feed parser — market reports and stock news."""

    FEEDS = [
        ("https://www.moneycontrol.com/rss/marketreports.xml", "MC Reports"),
        ("https://www.moneycontrol.com/rss/latestnews.xml", "MC Latest"),
    ]

    async def fetch_news(self, query: str = "", limit: int = 20) -> list[NewsItem]:
        items: list[NewsItem] = []
        for feed_url, source in self.FEEDS:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(feed_url)
                    resp.raise_for_status()
                fetched = _parse_rss_xml(resp.text, source, limit=limit // len(self.FEEDS) + 1)
                items.extend(fetched)
            except Exception as e:
                logger.warning("MC RSS fetch failed", source=source, error=str(e))
        return items[:limit]


class GDELTProvider(NewsProvider):
    """GDELT GDoc API — global structured news, free, no key required."""

    GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    async def fetch_news(self, query: str = "India stock market", limit: int = 20) -> list[NewsItem]:
        params = {
            "query": f"{query} sourcelang:eng",
            "mode": "artlist",
            "maxrecords": str(limit),
            "format": "json",
            "sort": "datedesc",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(self.GDELT_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("GDELT fetch failed", error=str(e))
            return []

        items = []
        for article in data.get("articles", []):
            try:
                published = datetime.strptime(
                    article.get("seendate", "20260101T000000Z"), "%Y%m%dT%H%M%SZ"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                published = datetime.now(timezone.utc)

            items.append(NewsItem(
                title=article.get("title", ""),
                source=article.get("domain", "GDELT"),
                url=article.get("url", ""),
                published=published,
                summary=article.get("title", ""),
                category="market",
            ))
        return items


# ── Aggregator Service ──────────────────────────────────────


class AggregatedNewsProvider(NewsProvider):
    """Merges feeds from ET, Mint, MC, and GDELT.

    - Removes duplicates by title hash
    - Tags NSE symbols (e.g. "Reliance" → "RELIANCE")
    - Sorts by publication time (newest first)
    """

    def __init__(self):
        self._providers: list[NewsProvider] = [
            EconomicTimesProvider(),
            LiveMintProvider(),
            MoneycontrolProvider(),
            GDELTProvider(),
        ]

    async def fetch_news(self, query: str = "India stock market", limit: int = 30) -> list[NewsItem]:
        all_items: list[NewsItem] = []

        for provider in self._providers:
            try:
                items = await provider.fetch_news(query=query, limit=limit // len(self._providers) + 2)
                all_items.extend(items)
            except Exception as e:
                logger.warning("Provider failed", provider=type(provider).__name__, error=str(e))

        # Deduplicate by title hash
        seen: set[str] = set()
        unique: list[NewsItem] = []
        for item in all_items:
            h = sha256(item.title.encode()).hexdigest()[:16]
            if h not in seen:
                seen.add(h)
                unique.append(item)

        # Tag symbols
        for item in unique:
            symbols = tag_symbols(f"{item.title} {item.summary}")
            if symbols:
                item.category = f"market:{','.join(symbols)}"

        # Sort newest first
        unique.sort(key=lambda x: x.published, reverse=True)
        return unique[:limit]

    async def fetch_for_symbol(self, symbol: str, limit: int = 20) -> list[NewsItem]:
        """Fetch news specifically related to a symbol."""
        # Map symbol back to company name for better search
        reverse_map = {v: k for k, v in _COMPANY_SYMBOL_MAP.items()}
        search_term = reverse_map.get(symbol.upper(), symbol)

        items = await self.fetch_news(query=search_term, limit=limit * 2)
        # Filter to items that actually mention the symbol
        filtered = [
            i for i in items
            if symbol.upper() in tag_symbols(f"{i.title} {i.summary}")
            or search_term.lower() in i.title.lower()
            or search_term.lower() in i.summary.lower()
        ]
        return filtered[:limit] if filtered else items[:limit]


# ── RSS XML Parser (shared) ────────────────────────────────


def _parse_rss_xml(xml_text: str, source: str, limit: int = 10) -> list[NewsItem]:
    """Parse standard RSS XML into NewsItem list. Handles malformed data gracefully."""
    items: list[NewsItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("Malformed RSS XML", source=source, error=str(e))
        return []

    for item_el in root.iter("item"):
        title = item_el.findtext("title", "").strip()
        link = item_el.findtext("link", "").strip()
        pub_date = item_el.findtext("pubDate", "").strip()
        desc = item_el.findtext("description", "").strip()

        if not title:
            continue

        # Parse date gracefully
        try:
            published = parsedate_to_datetime(pub_date).replace(tzinfo=timezone.utc)
        except Exception:
            published = datetime.now(timezone.utc)

        # Strip HTML tags from description
        clean_desc = re.sub(r"<[^>]+>", "", desc)[:300]

        items.append(NewsItem(
            title=title,
            source=source,
            url=link,
            published=published,
            summary=clean_desc,
            category="market",
        ))

        if len(items) >= limit:
            break

    return items


# ── Factory ─────────────────────────────────────────────────


def get_aggregated_news_provider() -> AggregatedNewsProvider:
    """Get the multi-source aggregated news provider."""
    return AggregatedNewsProvider()


def get_news_provider_by_name(name: str) -> NewsProvider:
    """Get a specific news provider by name."""
    providers: dict[str, type[NewsProvider]] = {
        "economic_times": EconomicTimesProvider,
        "livemint": LiveMintProvider,
        "moneycontrol": MoneycontrolProvider,
        "gdelt": GDELTProvider,
        "aggregated": AggregatedNewsProvider,
    }
    cls = providers.get(name.lower(), AggregatedNewsProvider)
    return cls()
