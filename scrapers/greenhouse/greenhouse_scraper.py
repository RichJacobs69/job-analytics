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


def load_title_patterns(config_path: Optional[Path] = None) -> List[str]:
    """
    Load job title filter patterns from YAML config.

    Args:
        config_path: Path to YAML config file. If None, uses default location.

    Returns:
        List of regex patterns for matching relevant job titles
    """
    if config_path is None:
        # Default: config/greenhouse_title_patterns.yaml relative to project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / 'config' / 'greenhouse_title_patterns.yaml'

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
        # Default: config/greenhouse_location_patterns.yaml relative to project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / 'config' / 'greenhouse_location_patterns.yaml'

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

    # Remote locations: match if "remote" is in target_patterns or if remote + target city
    if 'remote' in location_lower:
        # "Remote", "Remote - US", "Remote - London" all match if remote is in patterns
        return any(pattern.lower() in location_lower for pattern in target_patterns)

    # Standard substring matching
    return any(pattern.lower() in location_lower for pattern in target_patterns)


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
    # EU companies use job-boards.eu.greenhouse.io
    BASE_URLS = [
        "https://job-boards.greenhouse.io",                    # New domain (try first)
        "https://job-boards.eu.greenhouse.io",                 # EU domain
        "https://boards.greenhouse.io",                        # Legacy domain (fallback)
        "https://board.greenhouse.io",                         # Singular legacy variant
        "https://boards.greenhouse.io/embed/job_board?for=",   # Embed pattern (fallback for custom career sites)
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
                'nav[role="navigation"] a',
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
            pattern_config_path: Path to YAML config with title patterns (default: config/greenhouse_title_patterns.yaml)
            location_config_path: Path to YAML config with location patterns (default: config/greenhouse_location_patterns.yaml)
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
        max_retries: int = 3,
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

        # Try each base URL until one works
        for base_url in self.BASE_URLS:
            # Handle embed URL pattern (ends with ?for=) differently
            if base_url.endswith('?for='):
                url = f"{base_url}{company_slug}"
            else:
                url = f"{base_url}/{company_slug}"

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
                            logger.warning(f"[{company_slug}] No job listings found with any selector on {base_url}")
                            if page:
                                await page.close()
                            break  # Break retry loop, try next base URL (not a transient error)

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

                        logger.info(f"[{company_slug}] Successfully scraped {len(jobs)} jobs from {base_url}")
                        if self.filter_titles or self.filter_locations:
                            logger.info(f"[{company_slug}] Filtering: {self.filter_stats['jobs_scraped']} total, "
                                      f"{self.filter_stats['jobs_kept']} kept, "
                                      f"{self.filter_stats['jobs_filtered']} filtered ({filter_rate:.1f}%)")
                            if self.filter_titles:
                                logger.info(f"[{company_slug}]   - By title: {self.filter_stats['filtered_by_title']}")
                            if self.filter_locations:
                                logger.info(f"[{company_slug}]   - By location: {self.filter_stats['filtered_by_location']}")

                        return {
                            'jobs': jobs,
                            'stats': stats
                        }

                    except Exception as e:
                        logger.warning(f"[{company_slug}] Attempt {attempt + 1} on {base_url} failed: {str(e)[:100]}")
                        if page:
                            await page.close()
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2)

            except Exception as e:
                logger.warning(f"[{company_slug}] Failed with {base_url}: {str(e)[:100]}")
                continue  # Try next base URL

        logger.error(f"[{company_slug}] Failed to scrape on any base URL")
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
        max_pagination_iterations = 200  # Safety limit to prevent infinite loops
        pagination_iteration = 0

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

            for selector in selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    job_elements = elements
                    logger.info(f"[{company_slug}] Found {len(job_elements)} job listings using selector: {selector}")
                    break

            if not job_elements:
                # Give the page an extra chance to render after navigation
                await self._wait_for_listings(page, company_slug)
                for selector in selectors:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        job_elements = elements
                        logger.info(f"[{company_slug}] Found {len(job_elements)} job listings after wait using selector: {selector}")
                        break

            if not job_elements:
                logger.warning(f"[{company_slug}] No job listings found with any selector")
                break

            current_dom_job_count = len(job_elements)

            for job_element in job_elements:
                try:
                    # STEP 1: Extract basic job info WITHOUT description (fast, cheap)
                    job = await self._extract_job_listing(
                        job_element,
                        company_slug,
                        page,
                        fetch_description=False  # Don't fetch description yet
                    )

                    if not job or job.url in seen_urls:
                        continue

                    seen_urls.add(job.url)
                    self.filter_stats['jobs_scraped'] += 1

                    # STEP 2: Apply title filter
                    if self.filter_titles and self.title_patterns:
                        if not is_relevant_role(job.title, self.title_patterns):
                            # Job filtered out by title - don't fetch description
                            self.filter_stats['jobs_filtered'] += 1
                            self.filter_stats['filtered_by_title'] += 1
                            self.filter_stats['filtered_titles'].append(job.title)
                            logger.debug(f"[{company_slug}] Filtered by title: {job.title}")
                            continue

                    # STEP 3: Apply location filter
                    if self.filter_locations and self.location_patterns:
                        if not matches_target_location(job.location, self.location_patterns):
                            # Job filtered out by location - don't fetch description
                            self.filter_stats['jobs_filtered'] += 1
                            self.filter_stats['filtered_by_location'] += 1
                            self.filter_stats['filtered_locations'].append(job.location)
                            logger.debug(f"[{company_slug}] Filtered by location: {job.title} ({job.location})")
                            continue

                    # STEP 4: Job passed all filters - fetch full description (expensive)
                    self.filter_stats['jobs_kept'] += 1
                    job.description = await self._get_job_description(job.url)
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
                                    link_text = await link.text_content()
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
            try:
                generic_links = await page.query_selector_all('a, button')
                for link in generic_links:
                    try:
                        text = (await link.text_content() or '').strip()
                        if not text or not text.isdigit():
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
                    link_element = await job_element.query_selector('a[href*="/jobs/"]')
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
                    title_elem = await search_element.query_selector(selector)
                    if title_elem:
                        title = await title_elem.text_content()
                        break
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

            if not job_url:
                logger.debug(f"[{company_slug}] No job URL found for job element")
                return None

            # Job URLs from Greenhouse are already absolute (from stripe.com/jobs/listing/...)
            # or relative paths. If relative, join with a default base URL
            if not job_url.startswith('http'):
                job_url = urljoin(self.BASE_URLS[0], job_url)

            logger.debug(f"[{company_slug}] Extracted job: {title} -> {job_url}")

            # Extract job ID from URL
            # Patterns: /jobs/listing/{slug}/7306915 (Stripe) or /jobs/7306915 (standard Greenhouse)
            # Try to find a trailing numeric ID at the end of the URL path
            job_id = None
            # First try: numeric ID at end of URL path (handles /listing/slug/7306915)
            job_id_match = re.search(r'/(\d{6,})(?:\?|$)', job_url)  # 6+ digit ID at end
            if job_id_match:
                job_id = job_id_match.group(1)
            else:
                # Fallback: standard /jobs/ID pattern
                job_id_match = re.search(r'/jobs/(\d+)', job_url)
                job_id = job_id_match.group(1) if job_id_match else None

            # Try to get location from within the element using proper selectors
            location = "Unspecified"
            try:
                # Method 1: Try location-specific HTML selectors first
                location_selectors = self.SELECTORS['job_location']
                if isinstance(location_selectors, str):
                    location_selectors = [location_selectors]

                for selector in location_selectors:
                    try:
                        location_elem = await job_element.query_selector(selector)
                        if location_elem:
                            location_text = await location_elem.text_content()
                            if location_text and location_text.strip():
                                location = location_text.strip()
                                break
                    except:
                        continue

                # Method 2: If no HTML element found, extract from concatenated text
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

            # Department is optional, not critical to extract
            department = None

            # Get full description from job detail page (optional, expensive operation)
            # Uses page pooling to prevent browser crashes
            description = ""
            if fetch_description:
                description = await self._get_job_description(job_url)

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

    async def _get_job_description(self, job_url: str) -> str:
        """Navigate to job detail page and extract full description.

        Captures all job-related content sections (main description, work arrangements,
        benefits, etc.) to get the complete job posting.
        Uses concurrent page limiting to prevent browser crashes.
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
                    logger.debug(f"Found complete description: {len(description)} chars (main + {len(description_parts)-1} sections)")
                    return description

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
