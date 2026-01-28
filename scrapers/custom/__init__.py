"""
Custom Config Scraper Module

Provides config-driven scrapers for custom career sites that use proprietary
ATS platforms (Phenom, Taleo, custom) not covered by standard ATS integrations.

Supported sources:
- Google: XML feed (no Playwright needed)
- Apple, Netflix, JPMorgan: Playwright-based custom scrapers (Phase 2)
- Microsoft, Amazon, Meta: Planned (Phase 3)

Usage:
    from scrapers.custom import fetch_google_rss_jobs
    jobs, stats = fetch_google_rss_jobs()
"""

from scrapers.custom.google_rss_fetcher import (
    fetch_google_rss_jobs,
    GoogleJob,
    GOOGLE_RSS_URL,
)

__all__ = [
    'fetch_google_rss_jobs',
    'GoogleJob',
    'GOOGLE_RSS_URL',
]
