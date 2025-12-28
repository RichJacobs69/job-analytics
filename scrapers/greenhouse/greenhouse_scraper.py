"""
Greenhouse ATS Browser Automation Scraper

Scrapes job listings and full descriptions from Greenhouse-hosted career pages.
Uses Playwright to handle JavaScript rendering and dynamic content.

Usage:
    scraper = GreenhouseScraper()
    jobs = await scraper.scrape_company('stripe')

    # Or scrape all companies at once
    all_jobs = await scraper.scrape_all(['stripe', 'figma', 'github'])
"""

import asyncio
import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import re
from urllib.parse import urljoin
from pathlib import Path
import yaml
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
except ImportError:
    raise ImportError(
        "Playwright not installed. Install with: pip install playwright\n"
        "Then run: playwright install chromium"
    )

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import location extraction utilities
try:
    from pipeline.location_extractor import extract_locations
except ImportError:
    logger.warning("Could not import extract_locations - location extraction from descriptions disabled")
    extract_locations = None


def load_title_patterns(config_path: Optional[Path] = None) -> List[str]:
    """
    Load job title filter patterns from YAML config.

    Args:
        config_path: Path to YAML config file. If None, uses default location.

    Returns:
        List of regex patterns for matching relevant job titles
    """
    if config_path is None:
        # Default: config/greenhouse/title_patterns.yaml relative to project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / 'config' / 'greenhouse' / 'title_patterns.yaml'

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            patterns = config.get('relevant_title_patterns', [])
            logger.info(f"Loaded {len(patterns)} title filter patterns from {config_path}")
            return patterns
    except FileNotFoundError:
        logger.warning(f"Title patterns config not found at {config_path}. Filtering disabled.")
        return []
    except Exception as e:
        logger.warning(f"Failed to load title patterns: {e}. Filtering disabled.")
        return []


def load_location_patterns(config_path: Optional[Path] = None) -> List[str]:
    """
    Load target location filter patterns from YAML config.

    Args:
        config_path: Path to YAML config file. If None, uses default location.

    Returns:
        List of location strings to match (case-insensitive substring matching)
    """
    if config_path is None:
        # Default: config/greenhouse/location_patterns.yaml relative to project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / 'config' / 'greenhouse' / 'location_patterns.yaml'

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            patterns = config.get('target_locations', [])
            logger.info(f"Loaded {len(patterns)} location filter patterns from {config_path}")
            return patterns
    except FileNotFoundError:
        logger.warning(f"Location patterns config not found at {config_path}. Location filtering disabled.")
        return []
    except Exception as e:
        logger.warning(f"Failed to load location patterns: {e}. Location filtering disabled.")
        return []


def matches_target_location(location: str, target_patterns: List[str]) -> bool:
    """
    Check if job location matches target locations (London, NYC, Denver, Remote).

    Uses case-insensitive substring matching against target patterns.

    Args:
        location: Job location string (e.g., "London, UK", "New York, NY", "Remote")
        target_patterns: List of location substrings to match against

    Returns:
        True if location matches any target pattern
    """
    if not location or not target_patterns:
        return False

    location_lower = location.lower()
    patterns_lower = [p.lower() for p in target_patterns]

    # Split multi-location strings (e.g., "San Francisco, CA; New York, NY; Austin, TX").
    # We keep the full string plus split tokens to catch both combined and separated cases.
    tokens = [location_lower]
    split_tokens = [
        token.strip()
        for token in re.split(r'[;/|•\n]', location_lower)
        if token and token.strip()
    ]
    tokens.extend(split_tokens)

    return any(
        pattern in token
        for token in tokens
        for pattern in patterns_lower
    )


def is_relevant_role(title: str, patterns: List[str]) -> bool:
    """
    Check if job title matches Data/Product family patterns.

    Args:
        title: Job title string to evaluate
        patterns: List of regex patterns to match against

    Returns:
        True if title matches any pattern in the list

    Examples:
        >>> patterns = ['data (analyst|engineer)', 'product manager']
        >>> is_relevant_role('Senior Data Engineer', patterns)
        True
        >>> is_relevant_role('Account Executive', patterns)
        False
    """
    if not patterns:
        # No patterns loaded - accept all jobs (filtering disabled)
        return True

    title_lower = title.lower()
    for pattern in patterns:
        try:
            if re.search(pattern, title_lower):
                return True
        except re.error as e:
            logger.warning(f"Invalid regex pattern '{pattern}': {e}")
            continue

    return False


@dataclass
class Job:
    """Structured job posting"""
    company: str
    title: str
    location: str
    department: Optional[str] = None
    job_type: Optional[str] = None
    description: str = ""
    url: str = ""
    job_id: Optional[str] = None


class GreenhouseScraper:
    """
    Scrapes jobs from Greenhouse-hosted career boards using browser automation.

    Greenhouse jobs are rendered via JavaScript (React/Vue), so we need a real
    browser to load and parse the DOM. This scraper handles:
    - Navigation and page loading (supports both boards.greenhouse.io and job-boards.greenhouse.io)
    - Waiting for job listings to render
    - Pagination through all jobs
    - Individual job detail extraction
    - Error handling and retries
    """

    # Greenhouse has migrated to job-boards.greenhouse.io for some companies
    # Try both domains to find the correct one
    # Some companies (MongoDB, Databricks, etc.) only work with embed URLs
    # Order optimized based on discovery validation (2025-12-09):
    #   - job-boards.greenhouse.io: 87% success rate (47/54 companies)
    #   - embed format: 13% success rate (7/54 companies)
    #   - EU/legacy domains: 0% success rate (kept as fallback)
    BASE_URLS = [
        "https://job-boards.greenhouse.io",                    # Primary domain (87% success rate)
        "https://boards.greenhouse.io/embed/job_board?for=",   # Embed pattern (13% success rate - Unity, Coinbase, etc.)
        "https://boards.greenhouse.io",                        # Legacy domain (fallback)
        "https://board.greenhouse.io",                         # Singular legacy variant (fallback)
        "https://job-boards.eu.greenhouse.io",                 # EU domain (rare, check last)
    ]

    # CSS selectors for job listings page
    SELECTORS = {
        # Job listing containers - Greenhouse uses BEM naming (JobsListings__)
        'job_listing': [
            # Primary selectors for modern Greenhouse boards
            'a[class*="JobsListings__link"]',  # Job title link in BEM structure
            'tr:has(a[href*="/jobs/"])',  # Table row containing job link
            'a[href*="/jobs/"]',  # Direct job links (reliable fallback)
            'div[class*="JobsListingsSection"]',  # Job listings section container
            # Legacy fallbacks for older Greenhouse boards
            'div[class*="Opening"]',
            'div[class*="opening"]',
            '.opening',
        ],
        'job_title': [
            'a[class*="JobsListings__link"]',  # Greenhouse BEM naming
            'h2 a',
            'a[href*="/jobs/"]',
            'a[data-testid*="job"]',
        ],
        'job_location': [
            'span[class*="JobsListings__locationDisplayName"]',  # Greenhouse BEM location
            'span[class*="Location"]',
            'span[class*="location"]',
            '.location',
            'div[class*="meta"]',
            'p[class*="body__secondary"]',  # Airtable: <p class="body body__secondary body--metadata">
            'p.body__secondary',  # Airtable location (secondary paragraph)
            '[data-test-id*="location"]',  # Data test ID (some modern boards)
            '[class*="metadata"]',  # Metadata container
            '[class*="jobmeta"]',  # Job metadata section
            'div > span:last-of-type',  # Last span in container (sometimes location is trailing text)
        ],
        # Pagination selectors - Greenhouse uses different pagination styles
        'pagination': {
            'load_more_btn': [
                'button:has-text("Load More")',
                'button:has-text("Show More")',
                'a:has-text("Load More")',
            ],
            'next_btn': [
                'a:has-text("Next")',
                'button:has-text("Next")',
                'a[aria-label="Next"]',
                'a[aria-label*="Next"]',
                'button[aria-label="Next"]',
                'button[aria-label*="Next"]',
                'a.next',
                'button.next',
                'a[rel="next"]',
            ],
            'page_numbers': [
                'a[class*="pagination"]',
                'button[class*="pagination"]',
                'nav[class*="pagination"] a',
                'nav[aria-label*="Pagination"] a',
                # Removed: 'nav[role="navigation"] a' - too broad, matches category nav links
                'ul[class*="pagination"] a',
                'ul[aria-label*="Pagination"] a',
                'ol[class*="pagination"] a',
                'li[class*="page"] a',
            ]
        },

        # Individual job page selectors - be very broad to find the description
        'job_description': [
            # Stripe/modern Greenhouse boards use ArticleMarkdown class
            'div.ArticleMarkdown',
            'div[class*="ArticleMarkdown"]',
            # Try broader selectors that capture the entire job content area
            'div[class*="JobPostingDynamics"]',  # Actual Greenhouse class
            'div[class*="Content"]',
            'section[class*="job"]',
            'main',
            'div[class*="JobDescription"]',
            'div[class*="job-description"]',
            'article',
            'div[role="main"]',
        ],
        'job_department': [
            'span[class*="Department"]',
            '[class*="department"]',
        ],
        'job_type': '[class*="type"]',
    }

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 30000,
        max_concurrent_pages: int = 2,
        filter_titles: bool = True,
        filter_locations: bool = True,
        pattern_config_path: Optional[Path] = None,
        location_config_path: Optional[Path] = None,
        company_timeout_seconds: int = 300
    ):
        """
        Initialize scraper.

        Args:
            headless: Run browser in headless mode (no UI)
            timeout_ms: Timeout for page operations in milliseconds
            max_concurrent_pages: Max number of concurrent pages to prevent browser crashes
            filter_titles: Enable title-based filtering to reduce classification costs (default: True)
            filter_locations: Enable location-based filtering to reduce classification costs (default: True)
            pattern_config_path: Path to YAML config with title patterns (default: config/greenhouse/title_patterns.yaml)
            location_config_path: Path to YAML config with location patterns (default: config/greenhouse/location_patterns.yaml)
            company_timeout_seconds: Maximum time (in seconds) to spend scraping a single company (default: 300 = 5 min)
        """
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.max_concurrent_pages = max_concurrent_pages
        self.company_timeout_seconds = company_timeout_seconds
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.active_pages = 0

        # Title filtering configuration
        self.filter_titles = filter_titles
        self.title_patterns = load_title_patterns(pattern_config_path) if filter_titles else []

        # Location filtering configuration
        self.filter_locations = filter_locations
        self.location_patterns = load_location_patterns(location_config_path) if filter_locations else []

        # Pagination state tracking (prevent selector cycling)
        self.last_successful_next_selector: Optional[str] = None
        self.last_successful_load_more_selector: Optional[str] = None

        # Filtering statistics (tracked per scrape)
        self.reset_filter_stats()

        # URL cache from proven scraper runs (speeds up known companies)
        self.url_cache = self._load_url_cache()

    def _get_cache_path(self) -> Path:
        """Get path to scraper URL cache file."""
        project_root = Path(__file__).parent.parent.parent
        output_dir = project_root / 'output'
        output_dir.mkdir(exist_ok=True)
        return output_dir / 'greenhouse_scraper_cache.json'

    def _load_url_cache(self) -> Dict[str, str]:
        """Load URL cache from proven scraper runs.

        Returns:
            Dict mapping company_slug (lowercase) to successful URL
        """
        cache_path = self._get_cache_path()
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)

            cache = {slug.lower(): url for slug, url in cache_data.get('urls', {}).items()}

            if cache:
                logger.info(f"Loaded URL cache with {len(cache)} proven companies")
            return cache
        except FileNotFoundError:
            logger.debug("URL cache not found, will be created on first successful scrape")
            return {}
        except Exception as e:
            logger.warning(f"Failed to load URL cache: {e}")
            return {}

    def _update_url_cache(self, company_slug: str, successful_url: str):
        """Update URL cache with newly proven successful URL.

        Only adds URLs from actual successful scrapes (jobs extracted).

        Args:
            company_slug: Company slug (e.g., 'stripe')
            successful_url: URL that successfully scraped jobs
        """
        cache_path = self._get_cache_path()

        try:
            # Load existing cache
            try:
                with open(cache_path, 'r') as f:
                    cache_data = json.load(f)
            except FileNotFoundError:
                cache_data = {
                    'description': 'URL cache from proven Greenhouse scraper runs',
                    'last_updated': None,
                    'urls': {}
                }

            # Update or add entry
            slug_lower = company_slug.lower()
            if slug_lower in cache_data['urls']:
                logger.debug(f"Updated URL cache for {company_slug}: {successful_url}")
            else:
                logger.info(f"Added to URL cache: {company_slug} -> {successful_url}")

            cache_data['urls'][slug_lower] = successful_url
            cache_data['last_updated'] = datetime.now().isoformat()

            # Write back atomically
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)

            # Update in-memory cache
            self.url_cache[slug_lower] = successful_url

        except Exception as e:
            logger.warning(f"Failed to update URL cache for {company_slug}: {e}")

    def reset_filter_stats(self):
        """Reset filtering statistics for a new scrape."""
        self.filter_stats = {
            'jobs_scraped': 0,
            'jobs_kept': 0,
            'jobs_filtered': 0,
            'filtered_by_title': 0,
            'filtered_by_location': 0,
            'filtered_titles': [],
            'filtered_locations': [],
        }

    def reset_pagination_state(self):
        """Reset pagination tracking for a new company scrape."""
        self.last_successful_next_selector = None
        self.last_successful_load_more_selector = None

    async def init(self):
        """Initialize browser instance. Call before scraping."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        logger.info("Browser initialized")

    async def close(self):
        """Close browser instance. Call when done scraping."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")

    async def scrape_company(
        self,
        company_slug: str,
        max_retries: int = 1,
        max_jobs: Optional[int] = None
    ) -> Dict:
        """
        Scrape all jobs for a single company.

        Args:
            company_slug: Company slug for Greenhouse URL (e.g., 'stripe')
            max_retries: Number of retries on failure
            max_jobs: Maximum number of jobs to fetch (None = no limit)

        Returns:
            Dict with keys:
                - 'jobs': List[Job] - Job objects that passed filtering
                - 'stats': Dict - Filtering statistics (jobs_scraped, jobs_kept, jobs_filtered, etc.)
        """
        if not self.context:
            raise RuntimeError("Scraper not initialized. Call .init() first.")

        # Reset filter stats for this company
        self.reset_filter_stats()
        # Reset pagination state for this company
        self.reset_pagination_state()

        page = None

        # Check URL cache first (speeds up known companies)
        slug_lower = company_slug.lower()
        cached_url = self.url_cache.get(slug_lower)

        # Build URL list: cached URL first, then all BASE_URLS
        urls_to_try = []
        if cached_url:
            urls_to_try.append(cached_url)
            logger.info(f"[{company_slug}] Using cached URL: {cached_url}")

        # Add all BASE_URLS (will skip cached_url if already tried)
        for base_url in self.BASE_URLS:
            # Handle embed URL pattern (ends with ?for=) differently
            if base_url.endswith('?for='):
                url = f"{base_url}{company_slug}"
            else:
                url = f"{base_url}/{company_slug}"

            # Skip if this URL was already tried from cache
            if url != cached_url:
                urls_to_try.append(url)

        # Try each URL until one works
        for url in urls_to_try:
            try:
                for attempt in range(max_retries):
                    try:
                        page = await self.context.new_page()
                        logger.info(f"[{company_slug}] Attempt {attempt + 1}/{max_retries}: Loading {url}")

                        await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout_ms)

                        # Wait for job listings to appear (try multiple selectors)
                        listings_found = False
                        selectors = self.SELECTORS['job_listing']
                        if isinstance(selectors, str):
                            selectors = [selectors]

                        for selector in selectors:
                            try:
                                await page.wait_for_selector(selector, timeout=5000)
                                listings_found = True
                                logger.info(f"[{company_slug}] Found job listings using selector: {selector}")
                                break
                            except:
                                continue

                        if not listings_found:
                            logger.warning(f"[{company_slug}] No job listings found with any selector on {url}")
                            if page:
                                await page.close()
                            break  # Break retry loop, try next URL (not a transient error)

                        # Extract jobs (with filtering if enabled)
                        jobs = await self._extract_all_jobs(page, company_slug, max_jobs)

                        # Calculate additional stats
                        filter_rate = (self.filter_stats['jobs_filtered'] / self.filter_stats['jobs_scraped'] * 100) if self.filter_stats['jobs_scraped'] > 0 else 0
                        cost_savings_estimate = self.filter_stats['jobs_filtered'] * 0.00388  # Cost per classification

                        stats = {
                            **self.filter_stats,
                            'filter_rate': round(filter_rate, 1),
                            'cost_savings_estimate': f"${cost_savings_estimate:.2f}",
                            'filtered_titles_sample': self.filter_stats['filtered_titles'][:20],  # First 20 only
                            'filtered_locations_sample': self.filter_stats['filtered_locations'][:20],  # First 20 only
                        }

                        logger.info(f"[{company_slug}] Successfully scraped {len(jobs)} jobs from {url}")
                        if self.filter_titles or self.filter_locations:
                            logger.info(f"[{company_slug}] Filtering: {self.filter_stats['jobs_scraped']} total, "
                                      f"{self.filter_stats['jobs_kept']} kept, "
                                      f"{self.filter_stats['jobs_filtered']} filtered ({filter_rate:.1f}%)")
                            if self.filter_titles:
                                logger.info(f"[{company_slug}]   - By title: {self.filter_stats['filtered_by_title']}")
                            if self.filter_locations:
                                logger.info(f"[{company_slug}]   - By location: {self.filter_stats['filtered_by_location']}")

                        # Update URL cache with proven successful URL
                        self._update_url_cache(company_slug, url)

                        return {
                            'jobs': jobs,
                            'stats': stats
                        }

                    except Exception as e:
                        logger.warning(f"[{company_slug}] Attempt {attempt + 1} on {url} failed: {str(e)[:100]}")
                        if page:
                            await page.close()
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2)

            except Exception as e:
                logger.warning(f"[{company_slug}] Failed with {url}: {str(e)[:100]}")
                continue  # Try next URL

        logger.error(f"[{company_slug}] Failed to scrape on any URL")
        return {
            'jobs': [],
            'stats': self.filter_stats
        }

    async def _extract_all_jobs(self, page: Page, company_slug: str, max_jobs: Optional[int] = None) -> List[Job]:
        """
        Extract all jobs from listing page, handling pagination.

        If filtering is enabled, extracts job titles first, filters by pattern,
        then fetches full descriptions only for relevant jobs (60-70% cost savings).

        Args:
            page: Playwright page object
            company_slug: Company identifier
            max_jobs: Maximum number of jobs to fetch (None = no limit)
        """
        jobs = []
        seen_urls = set()
        visited_page_urls = set()  # Track visited pagination pages to prevent loops
        visited_page_numbers = set()  # Track clicked page numbers to prevent re-clicking
        max_pagination_iterations = 200  # Safety limit to prevent infinite loops
        pagination_iteration = 0
        last_dom_job_count = 0  # Track job count to detect infinite loops
        identical_count_iterations = 0  # Count consecutive iterations with same job count

        while True:
            pagination_iteration += 1
            if pagination_iteration > max_pagination_iterations:
                logger.warning(f"[{company_slug}] Reached max pagination iterations ({max_pagination_iterations}), stopping")
                break
            # Track the current page URL to avoid loops when pagination links point back
            try:
                visited_page_urls.add(page.url)
            except Exception:
                pass
            # Extract jobs from current view - try multiple selectors
            job_elements = []
            selectors = self.SELECTORS['job_listing']
            if isinstance(selectors, str):
                selectors = [selectors]

            # Pick the selector that returns the most elements rather than the first non-empty.
            # Some boards (e.g., Stripe) show only a subset with the primary selector but
            # expose the full list via a fallback selector (a[href*="/jobs/"]).
            max_found = 0
            best_selector = None
            for selector in selectors:
                elements = await page.query_selector_all(selector)
                if elements and len(elements) > max_found:
                    job_elements = elements
                    max_found = len(elements)
                    best_selector = selector

            if job_elements:
                logger.info(f"[{company_slug}] Found {len(job_elements)} job listings using selector: {best_selector}")

            if not job_elements:
                # Give the page an extra chance to render after navigation
                await self._wait_for_listings(page, company_slug)
                max_found = 0
                best_selector = None
                for selector in selectors:
                    elements = await page.query_selector_all(selector)
                    if elements and len(elements) > max_found:
                        job_elements = elements
                        max_found = len(elements)
                        best_selector = selector
                if job_elements:
                    logger.info(f"[{company_slug}] Found {len(job_elements)} job listings after wait using selector: {best_selector}")

                if not job_elements:
                    logger.warning(f"[{company_slug}] No job listings found with any selector")
                    break

            current_dom_job_count = len(job_elements)

            # INFINITE LOOP DETECTION: If we're seeing the same job count repeatedly, we're likely looping
            if current_dom_job_count == last_dom_job_count and current_dom_job_count > 0:
                identical_count_iterations += 1
                if identical_count_iterations >= 3:  # 3 consecutive iterations with same count = loop
                    logger.warning(f"[{company_slug}] Detected infinite loop (same job count {current_dom_job_count} for 3 iterations), stopping pagination")
                    break
            else:
                identical_count_iterations = 0  # Reset counter if job count changed
            last_dom_job_count = current_dom_job_count

            for job_element in job_elements:
                try:
                    # STEP 1: Extract basic job info WITHOUT description (fast, cheap)
                    # Add timeout to prevent hanging on problematic pages
                    try:
                        job = await asyncio.wait_for(
                            self._extract_job_listing(
                                job_element,
                                company_slug,
                                page,
                                fetch_description=False  # Don't fetch description yet
                            ),
                            timeout=5  # 5 second timeout per job extraction
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"[{company_slug}] Timeout extracting job listing (5s) - skipping job")
                        continue
                    except Exception as e:
                        logger.warning(f"[{company_slug}] Error extracting job listing: {str(e)[:100]}")
                        continue

                    if not job or job.url in seen_urls:
                        continue

                    seen_urls.add(job.url)
                    self.filter_stats['jobs_scraped'] += 1

                    # STEP 2: Apply title filter
                    if self.filter_titles and self.title_patterns:
                        try:
                            if not is_relevant_role(job.title, self.title_patterns):
                                # Job filtered out by title - don't fetch description
                                self.filter_stats['jobs_filtered'] += 1
                                self.filter_stats['filtered_by_title'] += 1
                                self.filter_stats['filtered_titles'].append(job.title)
                                logger.info(f"[{company_slug}] Filtered by title: '{job.title}'")
                                continue
                        except Exception as e:
                            logger.warning(f"[{company_slug}] Error filtering by title: {str(e)[:100]}")
                            continue

                    # STEP 3: Apply location filter
                    if self.filter_locations and self.location_patterns:
                        try:
                            if not matches_target_location(job.location, self.location_patterns):
                                # Job filtered out by location - don't fetch description
                                self.filter_stats['jobs_filtered'] += 1
                                self.filter_stats['filtered_by_location'] += 1
                                self.filter_stats['filtered_locations'].append(job.location)
                                logger.info(f"[{company_slug}] Filtered by location: '{job.title}' at '{job.location}'")
                                continue
                        except Exception as e:
                            logger.warning(f"[{company_slug}] Error filtering by location: {str(e)[:100]}")
                            continue

                    # STEP 4: Job passed all filters - fetch full description (expensive)
                    self.filter_stats['jobs_kept'] += 1

                    # Only fetch description if:
                    # 1. Filters are enabled (so we're limiting to a subset), OR
                    # 2. max_jobs is set (so we're limiting results anyway)
                    # Skip description fetching during pagination if no filters and no limit (allows full pagination)
                    if self.filter_titles or self.filter_locations or max_jobs:
                        job.description = await self._get_job_description(job.url, company_slug, job.job_id)

                    jobs.append(job)

                    # Check if we've reached max_jobs limit
                    if max_jobs and len(jobs) >= max_jobs:
                        logger.info(f"[{company_slug}] Reached max_jobs limit ({max_jobs}), stopping")
                        return jobs

                except Exception as e:
                    logger.warning(f"[{company_slug}] Failed to extract job: {str(e)[:100]}")
                    continue

            # Some modern Greenhouse boards lazy-load on scroll (no explicit pagination)
            if await self._try_infinite_scroll(page, company_slug, current_dom_job_count):
                continue

            # Check for pagination controls (try multiple methods)
            pagination_found = False

            # Method 1: Try "Load More" or "Show More" buttons
            # Prioritize last successful selector if available
            load_more_selectors = self.SELECTORS['pagination']['load_more_btn'].copy()
            if self.last_successful_load_more_selector and self.last_successful_load_more_selector in load_more_selectors:
                # Move successful selector to front
                load_more_selectors.remove(self.last_successful_load_more_selector)
                load_more_selectors.insert(0, self.last_successful_load_more_selector)

            for selector in load_more_selectors:
                try:
                    load_more = await page.query_selector(selector)
                    if load_more:
                        # Check if button is visible and enabled
                        is_visible = await load_more.is_visible()
                        is_enabled = await load_more.is_enabled()

                        if is_visible and is_enabled:
                            await load_more.click()
                            # Retry wait_for_listings with exponential backoff if it fails
                            wait_success = await self._wait_for_listings_with_retry(page, company_slug, max_retries=2)
                            if wait_success:
                                logger.info(f"[{company_slug}] Clicked Load More using selector: {selector}")
                                self.last_successful_load_more_selector = selector
                                pagination_found = True
                                break
                            else:
                                logger.warning(f"[{company_slug}] Load More clicked but listings failed to appear with selector: {selector}")
                except Exception as e:
                    logger.debug(f"[{company_slug}] Load More selector '{selector}' failed: {str(e)[:50]}")
                    continue

            if pagination_found:
                continue

            # Method 2: Try "Next" button/link
            # Prioritize last successful selector if available
            next_selectors = self.SELECTORS['pagination']['next_btn'].copy()
            if self.last_successful_next_selector and self.last_successful_next_selector in next_selectors:
                # Move successful selector to front
                next_selectors.remove(self.last_successful_next_selector)
                next_selectors.insert(0, self.last_successful_next_selector)

            for selector in next_selectors:
                try:
                    next_btn = await page.query_selector(selector)
                    if next_btn:
                        # Check if Next button exists and is enabled
                        is_visible = await next_btn.is_visible()
                        is_enabled = await next_btn.is_enabled()

                        if is_visible and is_enabled:
                            logger.debug(f"[{company_slug}] Attempting Next with selector: {selector}")
                            await next_btn.click()
                            # Retry wait_for_listings with exponential backoff if it fails
                            wait_success = await self._wait_for_listings_with_retry(page, company_slug, max_retries=2)
                            if wait_success:
                                logger.info(f"[{company_slug}] Clicked Next button using selector: {selector}")
                                self.last_successful_next_selector = selector
                                pagination_found = True
                                break
                            else:
                                logger.warning(f"[{company_slug}] Next button clicked but listings failed to appear with selector: {selector}")
                except Exception as e:
                    logger.debug(f"[{company_slug}] Next button selector '{selector}' failed: {str(e)[:50]}")
                    continue

            if pagination_found:
                continue

            # Method 3: Try page number links (find unvisited page numbers)
            # This is more complex - look for pagination links and find the next one
            for selector in self.SELECTORS['pagination']['page_numbers']:
                try:
                    page_links = await page.query_selector_all(selector)
                    if page_links:
                        # Try to find a page number we haven't visited
                        # Usually the current page has an "active" class or aria-current
                        for link in page_links:
                            try:
                                # Get the link href to track visited pages
                                link_href = await link.get_attribute('href')
                                if not link_href:
                                    continue

                                # Skip if we've already visited this page
                                if link_href in visited_page_urls:
                                    continue

                                # Check if this is NOT the current page
                                class_name = await link.get_attribute('class') or ''
                                aria_current = await link.get_attribute('aria-current') or ''

                                # Skip if it's the current/active page
                                if 'active' in class_name.lower() or 'current' in class_name.lower():
                                    continue
                                if aria_current == 'page':
                                    continue

                                # Check if it's visible and enabled
                                is_visible = await link.is_visible()
                                is_enabled = await link.is_enabled()

                                if is_visible and is_enabled:
                                    link_text = (await link.text_content() or '').strip()

                                    # Validate that this looks like a page number, not a category link
                                    # Accept: numeric ("2", "3"), or pagination keywords ("Next", "Previous", ">", ">>")
                                    is_numeric = link_text.isdigit()
                                    pagination_keywords = ['next', 'prev', 'previous', '>', '<', '>>', '<<', 'more']
                                    has_pagination_keyword = any(kw in link_text.lower() for kw in pagination_keywords)

                                    if not (is_numeric or has_pagination_keyword):
                                        # Skip non-pagination links (e.g., "Fraud Detection", "ComplyLaunch")
                                        continue

                                    visited_page_urls.add(link_href)  # Mark as visited before clicking
                                    await link.click()
                                    await self._wait_for_listings(page, company_slug)
                                    logger.info(f"[{company_slug}] Clicked page number: {link_text}")
                                    pagination_found = True
                                    break
                            except:
                                continue

                        if pagination_found:
                            break
                except Exception as e:
                    logger.debug(f"[{company_slug}] Page numbers selector '{selector}' failed: {str(e)[:50]}")
                    continue

            if pagination_found:
                continue

            # Method 4: Fallback - click any visible numeric page link that isn't active
            # ONLY try fallback if we haven't used Next button recently (to avoid loops)
            # The Next button is more reliable for pagination; fallback is for tables without Next
            if not self.last_successful_next_selector:
                # First, detect the current page number from active/current indicators
                current_page_num = 1
                try:
                    # Try multiple selectors to find active page indicator
                    active_links = await page.query_selector_all(
                        'a[aria-current="page"], button[aria-current="page"], '
                        'a.active, button.active, '
                        'li.active a, li.current a, '
                        'a[class*="active"], button[class*="active"], '
                        'a[class*="current"], button[class*="current"]'
                    )
                    for active_link in active_links:
                        active_text = (await active_link.text_content() or '').strip()
                        # Extract just the number part if it's mixed with text
                        for char in active_text:
                            if char.isdigit():
                                current_page_num = int(active_text.split()[0]) if active_text.split()[0].isdigit() else current_page_num
                                break
                        if current_page_num > 1:  # Found valid page number
                            break
                except Exception:
                    pass

                try:
                    generic_links = await page.query_selector_all('a, button')
                    for link in generic_links:
                        try:
                            text = (await link.text_content() or '').strip()
                            if not text or not text.isdigit():
                                continue

                            page_num = int(text)
                            # Don't click numeric links that go backwards, to same page, or already visited
                            if page_num <= current_page_num or page_num in visited_page_numbers:
                                continue

                            link_href = await link.get_attribute('href') or ''
                            class_name = await link.get_attribute('class') or ''
                            aria_current = await link.get_attribute('aria-current') or ''
                            aria_disabled = await link.get_attribute('aria-disabled') or ''

                            if link_href and link_href in visited_page_urls:
                                continue
                            if 'active' in class_name.lower() or 'current' in class_name.lower():
                                continue
                            if aria_current == 'page' or aria_disabled == 'true':
                                continue

                            is_visible = await link.is_visible()
                            is_enabled = await link.is_enabled()
                            if not (is_visible and is_enabled):
                                continue

                            if link_href:
                                visited_page_urls.add(link_href)
                            visited_page_numbers.add(page_num)  # Track this page number to prevent re-click
                            await link.click()
                            await self._wait_for_listings(page, company_slug)
                            logger.info(f"[{company_slug}] Clicked numeric page link via fallback: {text}")
                            pagination_found = True
                            break
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"[{company_slug}] Fallback numeric pagination failed: {str(e)[:50]}")

            if pagination_found:
                continue

            # No pagination found - we've reached the end
            logger.info(f"[{company_slug}] No more pagination controls found, scraping complete")
            break

        return jobs

    async def _try_infinite_scroll(self, page: Page, company_slug: str, previous_count: int) -> bool:
        """
        Handle boards that load additional jobs when scrolling to the bottom.

        Returns True if new job elements appear after scrolling.
        """
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

            selectors = self.SELECTORS['job_listing']
            if isinstance(selectors, str):
                selectors = [selectors]

            for selector in selectors:
                new_elements = await page.query_selector_all(selector)
                if new_elements and len(new_elements) > previous_count:
                    logger.info(f"[{company_slug}] Detected infinite scroll, loaded {len(new_elements) - previous_count} more jobs via {selector}")
                    return True
        except Exception as e:
            logger.debug(f"[{company_slug}] Infinite scroll detection failed: {str(e)[:80]}")

        return False

    async def _wait_for_listings(self, page: Page, company_slug: str, timeout_ms: int = 5000):
        """
        Wait for any job listing selector to appear after navigation/pagination.
        """
        selectors = self.SELECTORS['job_listing']
        if isinstance(selectors, str):
            selectors = [selectors]

        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=timeout_ms)
                logger.debug(f"[{company_slug}] Listings appeared with selector {selector}")
                return
            except Exception:
                continue

    async def _wait_for_listings_with_retry(self, page: Page, company_slug: str, max_retries: int = 2, base_timeout_ms: int = 5000) -> bool:
        """
        Wait for job listings to appear after pagination, with retry and exponential backoff.

        Args:
            page: Playwright page object
            company_slug: Company identifier
            max_retries: Number of retry attempts
            base_timeout_ms: Initial timeout in milliseconds

        Returns:
            True if listings appeared, False if all retries failed
        """
        selectors = self.SELECTORS['job_listing']
        if isinstance(selectors, str):
            selectors = [selectors]

        for attempt in range(max_retries):
            timeout_ms = base_timeout_ms * (2 ** attempt)  # Exponential backoff: 5000ms, 10000ms, etc.

            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=timeout_ms)
                    logger.debug(f"[{company_slug}] Listings appeared with selector {selector} (attempt {attempt + 1})")
                    return True
                except Exception as e:
                    logger.debug(f"[{company_slug}] Timeout waiting for selector {selector} (attempt {attempt + 1}, timeout={timeout_ms}ms): {str(e)[:60]}")
                    continue

            if attempt < max_retries - 1:
                logger.debug(f"[{company_slug}] Retry {attempt + 1}/{max_retries - 1}: waiting before next attempt...")
                await page.wait_for_timeout(1000)  # Wait 1 second before retry

        # Log detailed failure info
        logger.warning(f"[{company_slug}] Failed to find job listings after {max_retries} attempts. Possible causes: navigation failed, page structure changed, or timeout too short.")

        # Try to get current URL for debugging
        try:
            current_url = page.url
            logger.warning(f"[{company_slug}] Current page URL: {current_url}")
        except:
            pass

        return False

    async def _extract_job_listing(
        self,
        job_element,
        company_slug: str,
        page: Page,
        fetch_description: bool = True
    ) -> Optional[Job]:
        """
        Extract a single job from listing element.

        Args:
            job_element: DOM element containing job listing
            company_slug: Company identifier
            page: Playwright page object
            fetch_description: If True, fetch full description from detail page (expensive).
                             If False, only extract title/location from listing.
        """
        try:
            # Get URL - try as href attribute (if it's an <a> tag)
            job_url = await job_element.get_attribute('href')

            # If no href, try to find a link inside this element (table row case)
            link_element = None
            if not job_url:
                try:
                    # Try multiple selectors to handle different job board layouts:
                    # - Stripe/Greenhouse: a[href*="/jobs/"]
                    # - Datadog/Greenhouse embed: a[href*="/detail/"]
                    # - Fallback: any <a> tag (for other variations)
                    link_element = await job_element.query_selector('a[href*="/jobs/"], a[href*="/detail/"], a[href*="careers."], a')
                    if link_element:
                        job_url = await link_element.get_attribute('href')
                except:
                    pass

            # Get title from the link element (for table rows) or the element itself (for <a> tags)
            title = "Unknown"

            # Determine which element to search for title
            search_element = link_element if link_element else job_element

            # Try 1: Get title from job_title selector (more specific)
            job_title_selectors = self.SELECTORS.get('job_title', [])
            if isinstance(job_title_selectors, str):
                job_title_selectors = [job_title_selectors]

            for selector in job_title_selectors:
                try:
                    title_elem = await asyncio.wait_for(
                        search_element.query_selector(selector),
                        timeout=1  # 1 second timeout per selector search
                    )
                    if title_elem:
                        title = await asyncio.wait_for(
                            title_elem.text_content(),
                            timeout=1  # 1 second timeout for text extraction
                        )
                        break
                except asyncio.TimeoutError:
                    logger.debug(f"[{company_slug}] Timeout extracting title with selector: {selector}")
                    continue
                except:
                    continue

            # Try 2: If not found, get title from first <p> tag (handles Warby Parker table layout)
            if title == "Unknown" or not title:
                try:
                    p_elem = await search_element.query_selector('p:first-of-type')
                    if p_elem:
                        title = await p_elem.text_content()
                except:
                    pass

            # Try 3: Fallback to text_content() of first paragraph only (not entire element)
            if title == "Unknown" or not title:
                try:
                    first_p_text = await search_element.text_content()
                    # Split on double newline to separate title from location
                    if '\n\n' in first_p_text:
                        title = first_p_text.split('\n\n')[0]
                    else:
                        title = first_p_text
                except:
                    pass

            # Clean up title: remove "New" badge text and trailing whitespace
            title = title.strip() if title else "Unknown"
            # Remove " New" or "New" badge that appears after title in Greenhouse (with or without space)
            # Handles: "Manager New", "ManagerNew", "Center New", "CenterNew"
            title = re.sub(r'\s*New\s*$', '', title)
            # Remove any remaining newlines within title and normalize whitespace
            title = ' '.join(title.split())

            # Try 4: If title is generic button text, look at parent element for actual title
            # (Handles Skydio-style boards where <a> link text is "View & Apply" but title is in parent)
            generic_button_texts = ['view & apply', 'view and apply', 'apply', 'apply now', 'view', 'view job', 'learn more']
            if title.lower() in generic_button_texts:
                try:
                    parent = await asyncio.wait_for(
                        job_element.evaluate_handle('el => el.parentElement'),
                        timeout=1
                    )
                    # Try common title selectors in parent
                    parent_title_selectors = ['h2', 'h3', 'h4', '.job-title', '[class*="title"]', 'a[class*="title"]', 'span[class*="title"]']
                    for selector in parent_title_selectors:
                        try:
                            title_elem = await asyncio.wait_for(
                                parent.query_selector(selector),
                                timeout=1
                            )
                            if title_elem:
                                parent_title = await asyncio.wait_for(
                                    title_elem.text_content(),
                                    timeout=1
                                )
                                if parent_title and parent_title.strip() and parent_title.strip().lower() not in generic_button_texts:
                                    title = parent_title.strip()
                                    title = ' '.join(title.split())  # Normalize whitespace
                                    logger.debug(f"[{company_slug}] Found title in parent: {title}")
                                    break
                        except:
                            continue
                except asyncio.TimeoutError:
                    logger.debug(f"[{company_slug}] Timeout accessing parent for title")
                except:
                    pass

            if not job_url:
                logger.debug(f"[{company_slug}] No job URL found for job element")
                return None

            # Job URLs from Greenhouse are already absolute (from stripe.com/jobs/listing/...)
            # or relative paths. If relative, join with a default base URL
            if not job_url.startswith('http'):
                job_url = urljoin(self.BASE_URLS[0], job_url)

            # Fix Block-specific URL issue: Block's board has hrefs like /careers/jobs/ID
            # but the actual working URLs are /block/jobs/ID. Replace /careers/ with /{slug}/
            if '/careers/jobs/' in job_url and company_slug:
                job_url = job_url.replace('/careers/jobs/', f'/{company_slug}/jobs/')

            logger.debug(f"[{company_slug}] Extracted job: {title} -> {job_url}")

            # Extract job ID from URL - try multiple patterns
            # Patterns: gh_jid=XXX (custom pages), /jobs/XXX (standard), /listing/slug/XXX (Stripe)
            job_id = None
            # Pattern 1: gh_jid query parameter (custom career pages)
            job_id_match = re.search(r'[?&]gh_jid=(\d+)', job_url)
            if job_id_match:
                job_id = job_id_match.group(1)
            else:
                # Pattern 2: numeric ID at end of URL path (e.g., /listing/slug/7306915)
                job_id_match = re.search(r'/(\d{6,})(?:\?|$)', job_url)
                if job_id_match:
                    job_id = job_id_match.group(1)
                else:
                    # Pattern 3: standard /jobs/ID pattern
                    job_id_match = re.search(r'/jobs/(\d+)', job_url)
                    job_id = job_id_match.group(1) if job_id_match else None

            # Try to get location from within the element using proper selectors
            location = "Unspecified"
            try:
                # Method 1: Try location-specific HTML selectors first (in job_element and parent)
                location_selectors = self.SELECTORS['job_location']
                if isinstance(location_selectors, str):
                    location_selectors = [location_selectors]

                # Try searching within the job_element first
                for selector in location_selectors:
                    try:
                        location_elem = await asyncio.wait_for(
                            job_element.query_selector(selector),
                            timeout=1  # 1 second timeout per selector search
                        )
                        if location_elem:
                            location_text = await asyncio.wait_for(
                                location_elem.text_content(),
                                timeout=1  # 1 second timeout for text extraction
                            )
                            if location_text and location_text.strip():
                                location = location_text.strip()
                                break
                    except asyncio.TimeoutError:
                        logger.debug(f"[{company_slug}] Timeout extracting location with selector: {selector}")
                        continue
                    except:
                        continue

                # If not found in job_element, try the parent container
                # (Handles cases like Dojo where location is a sibling: <a>Title</a> <span class="location">...</span>)
                if location == "Unspecified":
                    try:
                        parent = await asyncio.wait_for(
                            job_element.evaluate_handle('el => el.parentElement'),
                            timeout=1  # 1 second timeout
                        )
                        for selector in location_selectors:
                            try:
                                location_elem = await asyncio.wait_for(
                                    parent.query_selector(selector),
                                    timeout=1  # 1 second timeout per selector search
                                )
                                if location_elem:
                                    location_text = await asyncio.wait_for(
                                        location_elem.text_content(),
                                        timeout=1  # 1 second timeout for text extraction
                                    )
                                    if location_text and location_text.strip():
                                        location = location_text.strip()
                                        break
                            except asyncio.TimeoutError:
                                logger.debug(f"[{company_slug}] Timeout extracting location from parent with selector: {selector}")
                                continue
                            except:
                                continue
                            if location != "Unspecified":
                                break
                    except asyncio.TimeoutError:
                        logger.debug(f"[{company_slug}] Timeout accessing parent element")
                    except:
                        pass

                # Method 3: Last resort - try to extract location from full job element text content
                # (Handles cases where location is mixed into the general text, like Wayve Greenhouse boards)
                if location == "Unspecified":
                    try:
                        full_text = await job_element.text_content()
                        if full_text:
                            # Look for patterns like "Sunnyvale, California" or "London, UK"
                            # Pattern: City, State/Country (with optional "USA")
                            location_match = re.search(
                                r'([A-Z][a-z]+(?: [A-Z][a-z]+)*),\s*([A-Z]{2}|[A-Z][a-z]+ [A-Z][a-z]+|[A-Za-z]+),?\s*(?:USA|US)?',
                                full_text
                            )
                            if location_match:
                                location = location_match.group(0).strip()
                                logger.debug(f"[{company_slug}] Extracted location from full text: '{location}'")
                    except:
                        pass

                # Method 4: If no HTML element found, extract from concatenated text
                # (Handles table layouts where title+location are in same element)
                if location == "Unspecified" and self.location_patterns:
                    title_lower = title.lower()
                    for pattern in self.location_patterns:
                        pattern_lower = pattern.lower()
                        if pattern_lower in title_lower:
                            # Found location pattern in text - extract surrounding context
                            # This handles cases like "Product ManagerNYC Global HQ"
                            idx = title_lower.find(pattern_lower)
                            # Extract from pattern start to end of string as location
                            location = title[idx:].strip()
                            logger.debug(f"[{company_slug}] Extracted location from text: '{location}' using pattern '{pattern}'")
                            break
            except:
                pass

            # NOTE: Location will be populated from job description later if fetch_description=True
            # and current extraction returned "Unspecified" (see post-extraction location mining below)

            # Department is optional, not critical to extract
            department = None

            # Get full description from job detail page (optional, expensive operation)
            # Uses page pooling to prevent browser crashes
            description = ""
            if fetch_description:
                description = await self._get_job_description(job_url, company_slug, job_id)

                # CRITICAL: Detect and skip bot challenge pages (Cloudflare, etc.)
                # Bot detection pages are typically short (<500 chars) with challenge keywords
                is_short = len(description) < 500
                has_challenge = 'challenge-error' in description.lower() or 'verify you are human' in description.lower()
                has_js_warning = 'enable javascript and cookies' in description.lower()

                if is_short and (has_challenge or has_js_warning):
                    logger.warning(f"[{company_slug}] Bot detection page detected for {job_url} - skipping job")
                    return None  # Skip this job entirely

                # POST-EXTRACTION LOCATION MINING:
                # If location still "Unspecified" after initial extraction, mine from description
                if location == "Unspecified" and description and extract_locations:
                    location = self._extract_location_from_description(description, company_slug)

            return Job(
                company=company_slug,
                title=title,
                location=location,
                department=department,
                job_type=None,
                description=description,
                url=job_url,
                job_id=job_id,
            )

        except Exception as e:
            logger.warning(f"[{company_slug}] Error extracting job: {str(e)}")
            return None

    def _extract_location_from_description(self, description: str, company_slug: str) -> str:
        """
        Extract location from job description text.

        Looks for location mentions in common formats like "Location: ...", "Based in: ...", etc.
        Uses extract_locations to parse found location strings.

        Args:
            description: Full job description text
            company_slug: Company slug for logging

        Returns:
            Extracted location string, or "Unspecified" if not found
        """
        if not description or not extract_locations:
            return "Unspecified"

        try:
            # Look for common location patterns in description
            # Patterns: "Location: San Francisco, CA", "Based in: London, UK", "Locations: NYC or Remote", etc.
            location_patterns = [
                r'(?:Location|Based|Headquarters|Office|Offices|Duty\s+(?:station|location))s?:\s*([^\n]+)',
                r'(?:Location|Based|Work\s+(?:location|arrangement)):\s*([^\n]+)',
                r'^(?:Location|Based|Work\s+Location):\s*(.+?)(?:\n|$)',
            ]

            description_lower = description.lower()

            for pattern in location_patterns:
                matches = re.finditer(pattern, description, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    location_str = match.group(1).strip()

                    # Clean up: remove bullet points, extra whitespace, etc.
                    location_str = re.sub(r'^[\s•\-]*', '', location_str)
                    location_str = re.sub(r'[\s•\-]*$', '', location_str)
                    location_str = ' '.join(location_str.split())  # Normalize whitespace

                    # Skip generic/placeholder text
                    if location_str and len(location_str) > 2 and len(location_str) < 200:
                        if not any(skip in location_str.lower() for skip in ['tbd', 'to be', 'flexible', 'varies']):
                            # Found a valid location mention
                            logger.debug(f"[{company_slug}] Extracted location from description: '{location_str}'")
                            return location_str

            # If pattern matching didn't work, try looking for city names in the description
            # This is a fallback that looks for known city names
            if self.location_patterns:
                description_text = ' ' + description + ' '  # Add space padding for word boundaries
                for pattern in self.location_patterns:
                    # Use word boundaries to find whole city mentions
                    if re.search(r'\b' + re.escape(pattern) + r'\b', description_text, re.IGNORECASE):
                        logger.debug(f"[{company_slug}] Found location pattern in description: '{pattern}'")
                        return pattern

            return "Unspecified"

        except Exception as e:
            logger.debug(f"[{company_slug}] Error extracting location from description: {str(e)[:50]}")
            return "Unspecified"

    def _is_valid_job_content(self, text: str) -> bool:
        """
        Validate that extracted text is actual job content, not garbage.

        Returns False for:
        - Empty or too short content
        - CSS code
        - Navigation/footer text without job content
        - Bot detection pages
        """
        if not text or len(text.strip()) < 200:
            return False

        text_lower = text.lower()

        # Check for garbage patterns (CSS, nav, bot detection)
        garbage_patterns = [
            '--grid-', '--sqs-', 'var(--', 'grid-template', '@media',
            '.fe-', '.sqs-block', 'minmax(',  # CSS
            'privacy policy', 'terms of service', 'cookie notice',  # Footer
            'challenge-error', 'verify you are human', 'enable javascript',  # Bot
        ]
        has_garbage = any(pattern in text_lower for pattern in garbage_patterns)

        # Check for job content indicators
        job_patterns = [
            'responsib', 'requirement', 'qualif', 'experience',
            'you will', 'the role', 'about us', 'the team',
            'skills', 'benefits', 'salary', 'compensation',
        ]
        has_job_content = sum(1 for p in job_patterns if p in text_lower) >= 2

        # Valid if has job content and minimal garbage
        # Or if has job content even with some garbage (can be cleaned later)
        return has_job_content

    async def _get_job_description(self, job_url: str, company_slug: str = None, job_id: str = None) -> str:
        """Navigate to job detail page and extract full description.

        Captures all job-related content sections (main description, work arrangements,
        benefits, etc.) to get the complete job posting.
        Uses concurrent page limiting to prevent browser crashes.

        If the page redirects away from greenhouse.io or returns invalid content,
        automatically tries the embed URL pattern as fallback.
        """
        detail_page = None
        try:
            # Wait if too many pages are open
            while self.active_pages >= self.max_concurrent_pages:
                await asyncio.sleep(0.5)

            self.active_pages += 1
            detail_page = await self.context.new_page()

            try:
                await detail_page.goto(job_url, wait_until='domcontentloaded', timeout=self.timeout_ms)
            except Exception as e:
                logger.debug(f"Failed to navigate to {job_url}: {str(e)[:50]}")
                return ""

            # Wait for JavaScript rendering (increased from 0.5s to 2s for better reliability)
            await asyncio.sleep(2)

            # Check if we were redirected away from greenhouse.io
            final_url = detail_page.url
            redirected_away = 'greenhouse.io' not in final_url.lower()

            # First, try to get text from the main article/content section
            # (handles most Stripe job postings with .ArticleMarkdown)
            selectors = self.SELECTORS['job_description']
            if isinstance(selectors, str):
                selectors = [selectors]

            description_parts = []

            # Try primary selectors for main job description
            found_main = False
            for selector in selectors:
                if found_main:
                    break
                try:
                    elements = await detail_page.query_selector_all(selector)
                    if not elements:
                        logger.debug(f"Selector '{selector}' found no elements")
                        continue

                    desc_elem = await detail_page.query_selector(selector)
                    if desc_elem:
                        text = await desc_elem.text_content()
                        if text and len(text.strip()) > 200:
                            description_parts.append(text)
                            found_main = True
                            logger.info(f"Found main description using '{selector}': {len(text)} chars")
                        else:
                            logger.debug(f"Selector '{selector}' found text but too short: {len(text) if text else 0} chars")
                except Exception as e:
                    logger.debug(f"Selector '{selector}' failed: {str(e)[:50]}")
                    continue

            # Now collect additional job details from section elements
            # (Hybrid work, Pay & benefits, In-office expectations, etc.)
            try:
                sections = await detail_page.query_selector_all('section')

                for section in sections:
                    try:
                        # Skip navigation/footer sections (very small)
                        text = await section.text_content()
                        if len(text) < 50:
                            continue

                        # Get section header to identify content
                        header = await section.query_selector('h1, h2, h3')
                        header_text = ""
                        if header:
                            header_text = await header.text_content()
                            header_text = header_text.strip() if header_text else ""

                        # Include sections that appear to be job-related
                        # (Hybrid work, Benefits, Requirements, etc.)
                        job_related_keywords = [
                            'hybrid', 'remote', 'work', 'benefits', 'pay', 'compensation',
                            'requirements', 'responsibilities', 'team', 'location',
                            'expectations', 'office', 'in-office'
                        ]

                        is_job_related = any(
                            keyword in header_text.lower()
                            for keyword in job_related_keywords
                        ) or header_text.lower().startswith(('who', 'what', 'about'))

                        if is_job_related and len(text) > 50:
                            # Add section header if it has one
                            if header_text and header_text not in [' '.join(p.split())[:len(header_text)]
                                                                     for p in description_parts]:
                                description_parts.append(header_text)
                            description_parts.append(text)
                    except:
                        continue
            except:
                pass

            # FALLBACK: If still no description, try getting entire body text
            if not description_parts or not found_main:
                logger.warning(f"No description found with primary selectors, trying body fallback for {job_url}")
                try:
                    body = await detail_page.query_selector('body')
                    if body:
                        text = await body.text_content()
                        if text and len(text.strip()) > 500:
                            # Clean up the text (remove extra whitespace)
                            text = ' '.join(text.split())
                            description_parts.append(text)
                            logger.info(f"Using body fallback: {len(text)} chars")
                except Exception as e:
                    logger.debug(f"Body fallback also failed: {str(e)[:50]}")

            # Combine all parts and clean up
            if description_parts:
                description = '\n\n'.join(description_parts)
                description = ' '.join(description.split())  # Normalize whitespace

                if len(description) > 200:
                    # Validate content quality
                    if self._is_valid_job_content(description):
                        logger.debug(f"Found complete description: {len(description)} chars (main + {len(description_parts)-1} sections)")
                        return description
                    else:
                        logger.warning(f"Content validation failed for {job_url} - content has garbage or missing job keywords")

            # EMBED URL FALLBACK: Try if redirected away or content invalid
            if (redirected_away or not description_parts or not self._is_valid_job_content('\n'.join(description_parts))) and company_slug and job_id:
                logger.info(f"Trying embed URL fallback for {company_slug} job {job_id}")
                try:
                    embed_url = f"https://boards.greenhouse.io/embed/job_app?for={company_slug}&token={job_id}"
                    await detail_page.goto(embed_url, wait_until='domcontentloaded', timeout=self.timeout_ms)
                    await asyncio.sleep(2)

                    # Check we stayed on greenhouse
                    if 'greenhouse.io' in detail_page.url:
                        body = await detail_page.query_selector('body')
                        if body:
                            embed_text = await body.text_content()
                            if embed_text and self._is_valid_job_content(embed_text):
                                embed_text = ' '.join(embed_text.split())
                                logger.info(f"Embed URL fallback succeeded: {len(embed_text)} chars")
                                return embed_text
                            else:
                                logger.debug(f"Embed URL returned invalid content")
                except Exception as e:
                    logger.debug(f"Embed URL fallback failed: {str(e)[:50]}")

            logger.warning(f"No substantial description found for {job_url} after all attempts")
            return ""

        except Exception as e:
            logger.warning(f"Failed to get description for {job_url}: {str(e)[:100]}")
            return ""

        finally:
            if detail_page:
                try:
                    await detail_page.close()
                except:
                    pass
                self.active_pages -= 1

    async def scrape_all(
        self,
        company_slugs: List[str],
        on_company_complete=None
    ) -> Dict[str, Dict]:
        """
        Scrape multiple companies sequentially with timeout protection.

        Supports incremental processing via callback - enables writing data
        to database after each company instead of waiting for all to complete.

        Args:
            company_slugs: List of company slugs
            on_company_complete: Optional callback function(company_slug, result)
                                called after each company completes.
                                Enables incremental database writes for resilience.
                                If callback raises exception, company is marked as failed.

        Returns:
            Dict mapping company_slug to dict with 'jobs' and 'stats'

        Example with incremental writes:
            async def process_company(company_slug, result):
                # Write raw jobs to DB
                for job in result['jobs']:
                    insert_raw_job_upsert(...)
                # Classify and store enriched jobs
                ...

            results = await scraper.scrape_all(companies, on_company_complete=process_company)
        """
        results = {}
        skipped_companies = []

        for company_slug in company_slugs:
            try:
                # Wrap scrape_company call with timeout
                result = await asyncio.wait_for(
                    self.scrape_company(company_slug),
                    timeout=self.company_timeout_seconds
                )
                results[company_slug] = result

                # INCREMENTAL PROCESSING: Call callback after company completes
                # This enables writing to DB immediately instead of waiting for all companies
                if on_company_complete:
                    try:
                        # Support both sync and async callbacks
                        if asyncio.iscoroutinefunction(on_company_complete):
                            await on_company_complete(company_slug, result)
                        else:
                            on_company_complete(company_slug, result)
                    except Exception as callback_error:
                        logger.error(f"[{company_slug}] Callback failed: {str(callback_error)[:100]}")
                        # Mark company as failed if callback fails
                        results[company_slug]['stats']['callback_error'] = str(callback_error)[:100]
                        skipped_companies.append(f"{company_slug} (callback failed)")

                await asyncio.sleep(1)  # Rate limit between companies

            except asyncio.TimeoutError:
                logger.warning(f"[{company_slug}] TIMEOUT after {self.company_timeout_seconds}s - skipping company")
                skipped_companies.append(company_slug)
                results[company_slug] = {
                    'jobs': [],
                    'stats': {
                        'jobs_scraped': 0,
                        'jobs_kept': 0,
                        'jobs_filtered': 0,
                        'error': f'TIMEOUT after {self.company_timeout_seconds}s'
                    }
                }
            except Exception as e:
                logger.error(f"[{company_slug}] Unexpected error: {str(e)[:100]} - skipping company")
                skipped_companies.append(company_slug)
                results[company_slug] = {
                    'jobs': [],
                    'stats': {
                        'jobs_scraped': 0,
                        'jobs_kept': 0,
                        'jobs_filtered': 0,
                        'error': str(e)[:100]
                    }
                }

        if skipped_companies:
            logger.warning(f"Skipped {len(skipped_companies)} companies due to timeout/error: {skipped_companies}")

        return results


async def main():
    """Example usage with title filtering"""

    test_companies = [
        'stripe',
        'figma',
        'github',
    ]

    # Initialize scraper with filtering enabled (default)
    scraper = GreenhouseScraper(headless=True, filter_titles=True)

    try:
        await scraper.init()
        results = await scraper.scrape_all(test_companies)

        # Print results with filtering stats
        total_scraped = 0
        total_kept = 0
        total_filtered = 0

        for company, result in results.items():
            jobs = result['jobs']
            stats = result['stats']

            print(f"\n{'='*70}")
            print(f"{company.upper()}: {len(jobs)} jobs kept")
            print('='*70)

            # Print filtering stats
            if stats['jobs_scraped'] > 0:
                print(f"Total scraped: {stats['jobs_scraped']}")
                print(f"Kept (relevant): {stats['jobs_kept']} ({100 - stats['filter_rate']:.1f}%)")
                print(f"Filtered out: {stats['jobs_filtered']} ({stats['filter_rate']}%)")
                print(f"Cost savings: {stats['cost_savings_estimate']}")

                total_scraped += stats['jobs_scraped']
                total_kept += stats['jobs_kept']
                total_filtered += stats['jobs_filtered']

            # Show sample jobs
            for i, job in enumerate(jobs[:2], 1):  # Show first 2
                print(f"\n[{i}] {job.title}")
                print(f"    Location: {job.location}")
                print(f"    Department: {job.department}")
                print(f"    Description (first 300 chars): {job.description[:300]}...")

        # Summary
        print(f"\n{'='*70}")
        print("OVERALL SUMMARY")
        print('='*70)
        print(f"Total jobs scraped: {total_scraped}")
        print(f"Total jobs kept: {total_kept}")
        print(f"Total filtered out: {total_filtered}")
        if total_scraped > 0:
            overall_filter_rate = (total_filtered / total_scraped * 100)
            print(f"Overall filter rate: {overall_filter_rate:.1f}%")
            print(f"Total cost savings: ${total_filtered * 0.00388:.2f}")

        # Save to JSON for verification
        output = {
            company: {
                'jobs': [asdict(j) for j in result['jobs']],
                'stats': result['stats']
            }
            for company, result in results.items()
        }

        with open('greenhouse_scrape_results.json', 'w') as f:
            json.dump(output, f, indent=2, default=str)

        print("\n\nResults saved to greenhouse_scrape_results.json")

    finally:
        await scraper.close()


if __name__ == '__main__':
    asyncio.run(main())
