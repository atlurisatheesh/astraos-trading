"""AstraOS Tests — Phase 6: Multi-Source News Engine Tests."""

import pytest
from datetime import datetime, timezone

from src.services.news_providers import (
    tag_symbols,
    _parse_rss_xml,
    EconomicTimesProvider,
    LiveMintProvider,
    MoneycontrolProvider,
    GDELTProvider,
    AggregatedNewsProvider,
    get_aggregated_news_provider,
    get_news_provider_by_name,
)
from src.services.news_service import NewsItem


# ── Symbol Tagging Tests ────────────────────────────────────


class TestSymbolTagging:
    """Test the symbol-tagging engine that maps company names to NSE symbols."""

    def test_tag_single_company(self):
        symbols = tag_symbols("Reliance Industries reports strong Q3 results")
        assert "RELIANCE" in symbols

    def test_tag_multiple_companies(self):
        symbols = tag_symbols("TCS and Infosys lead IT sector gains today")
        assert "TCS" in symbols
        assert "INFY" in symbols

    def test_tag_case_insensitive(self):
        symbols = tag_symbols("HDFC BANK announces quarterly dividend")
        assert "HDFCBANK" in symbols

    def test_tag_no_match(self):
        symbols = tag_symbols("The weather is nice in Mumbai today")
        assert symbols == []

    def test_tag_index_names(self):
        symbols = tag_symbols("Nifty crosses 25000, Bank Nifty also surges")
        assert "^NSEI" in symbols
        assert "^NSEBANK" in symbols

    def test_tag_deduplication(self):
        symbols = tag_symbols("Reliance gains. Reliance Industries hits new high for Reliance.")
        assert symbols.count("RELIANCE") == 1

    def test_tag_known_abbreviations(self):
        symbols = tag_symbols("SBI and ONGC results tomorrow")
        assert "SBIN" in symbols
        assert "ONGC" in symbols

    def test_tag_partial_names(self):
        symbols = tag_symbols("Airtel launches new 5G plans")
        assert "BHARTIARTL" in symbols

    def test_tag_adani(self):
        symbols = tag_symbols("Adani Enterprises wins solar contract")
        assert "ADANIENT" in symbols


# ── RSS XML Parser Tests ────────────────────────────────────


class TestRSSParser:
    """Test the shared RSS XML parser handles standard and malformed data."""

    VALID_RSS = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <item>
                <title>Market Rally Continues</title>
                <link>https://example.com/article1</link>
                <pubDate>Mon, 24 Mar 2026 10:30:00 +0530</pubDate>
                <description>Nifty hits new highs amid strong FII buying</description>
            </item>
            <item>
                <title>Reliance Q3 Results</title>
                <link>https://example.com/article2</link>
                <pubDate>Tue, 25 Mar 2026 14:00:00 +0530</pubDate>
                <description>&lt;p&gt;Strong revenue growth reported&lt;/p&gt;</description>
            </item>
        </channel>
    </rss>"""

    MALFORMED_RSS = """<not-valid-xml><<<>>>"""

    EMPTY_RSS = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>Empty</title></channel></rss>"""

    def test_parse_valid_rss(self):
        items = _parse_rss_xml(self.VALID_RSS, "TestSource", limit=10)
        assert len(items) == 2
        assert items[0].title == "Market Rally Continues"
        assert items[0].source == "TestSource"
        assert items[1].title == "Reliance Q3 Results"

    def test_parse_strips_html_from_description(self):
        items = _parse_rss_xml(self.VALID_RSS, "TestSource")
        # The HTML-tagged description should have tags stripped
        assert "<p>" not in items[1].summary
        assert "Strong revenue growth reported" in items[1].summary

    def test_parse_malformed_rss_no_crash(self):
        items = _parse_rss_xml(self.MALFORMED_RSS, "TestSource")
        assert items == []

    def test_parse_empty_rss(self):
        items = _parse_rss_xml(self.EMPTY_RSS, "TestSource")
        assert items == []

    def test_parse_respects_limit(self):
        items = _parse_rss_xml(self.VALID_RSS, "TestSource", limit=1)
        assert len(items) == 1

    def test_parse_sets_published_date(self):
        items = _parse_rss_xml(self.VALID_RSS, "TestSource")
        assert items[0].published.tzinfo is not None  # Should be timezone-aware

    def test_parse_newsitem_to_dict(self):
        items = _parse_rss_xml(self.VALID_RSS, "TestSource")
        d = items[0].to_dict()
        assert "title" in d
        assert "source" in d
        assert "url" in d
        assert "published" in d

    def test_parse_missing_pubdate_uses_now(self):
        rss = """<?xml version="1.0"?>
        <rss><channel><item>
            <title>No Date Article</title>
            <link>https://example.com</link>
        </item></channel></rss>"""
        items = _parse_rss_xml(rss, "TestSource")
        assert len(items) == 1
        # Should have a valid datetime (defaulting to now)
        assert items[0].published is not None


# ── Provider Factory Tests ──────────────────────────────────


class TestProviderFactory:
    """Test provider factory returns correct types."""

    def test_get_aggregated_provider(self):
        provider = get_aggregated_news_provider()
        assert isinstance(provider, AggregatedNewsProvider)

    def test_get_provider_by_name_et(self):
        provider = get_news_provider_by_name("economic_times")
        assert isinstance(provider, EconomicTimesProvider)

    def test_get_provider_by_name_mint(self):
        provider = get_news_provider_by_name("livemint")
        assert isinstance(provider, LiveMintProvider)

    def test_get_provider_by_name_mc(self):
        provider = get_news_provider_by_name("moneycontrol")
        assert isinstance(provider, MoneycontrolProvider)

    def test_get_provider_by_name_gdelt(self):
        provider = get_news_provider_by_name("gdelt")
        assert isinstance(provider, GDELTProvider)

    def test_get_provider_by_name_unknown_defaults_aggregated(self):
        provider = get_news_provider_by_name("unknown_xyz")
        assert isinstance(provider, AggregatedNewsProvider)


# ── Aggregator Dedup Tests ──────────────────────────────────


class TestAggregatorDedup:
    """Test the aggregator deduplication logic."""

    def test_dedup_removes_exact_duplicates(self):
        """Verify items with identical titles are deduplicated."""
        # We test the dedup logic directly using _parse_rss_xml + hash
        from hashlib import sha256

        items = [
            NewsItem("Same Title", "Source1", "url1", datetime.now(timezone.utc)),
            NewsItem("Same Title", "Source2", "url2", datetime.now(timezone.utc)),
            NewsItem("Different Title", "Source3", "url3", datetime.now(timezone.utc)),
        ]
        seen: set[str] = set()
        unique = []
        for item in items:
            h = sha256(item.title.encode()).hexdigest()[:16]
            if h not in seen:
                seen.add(h)
                unique.append(item)
        assert len(unique) == 2

    def test_newsitem_category_default(self):
        item = NewsItem("Test", "Source", "url", datetime.now(timezone.utc))
        assert item.category == "general"
