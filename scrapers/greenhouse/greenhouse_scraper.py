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
    BASE_URLS = [
        "https://job-boards.greenhouse.io",                    # New domain (try first)
        "https://boards.greenhouse.io",                        # Legacy domain (fallback)
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
                'button[aria-label="Next"]',
                'a.next',
                'button.next',
            ],
            'page_numbers': [
                'a[class*="pagination"]',
                'button[class*="pagination"]',
                'nav[class*="pagination"] a',
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
        pattern_config_path: Optional[Path] = None
    ):
        """
        Initialize scraper.

        Args:
            headless: Run browser in headless mode (no UI)
            timeout_ms: Timeout for page operations in milliseconds
            max_concurrent_pages: Max number of concurrent pages to prevent browser crashes
            filter_titles: Enable title-based filtering to reduce classification costs (default: True)
            pattern_config_path: Path to YAML config with title patterns (default: config/greenhouse_title_patterns.yaml)
        """
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.max_concurrent_pages = max_concurrent_pages
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.active_pages = 0

        # Title filtering configuration
        self.filter_titles = filter_titles
        self.title_patterns = load_title_patterns(pattern_config_path) if filter_titles else []

        # Filtering statistics (tracked per scrape)
        self.reset_filter_stats()

    def reset_filter_stats(self):
        """Reset filtering statistics for a new scrape."""
        self.filter_stats = {
            'jobs_scraped': 0,
            'jobs_kept': 0,
            'jobs_filtered': 0,
            'filtered_titles': [],
        }

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
                            continue  # Try next base URL

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
                        }

                        logger.info(f"[{company_slug}] Successfully scraped {len(jobs)} jobs from {base_url}")
                        if self.filter_titles:
                            logger.info(f"[{company_slug}] Filtering: {self.filter_stats['jobs_scraped']} total, "
                                      f"{self.filter_stats['jobs_kept']} kept, "
                                      f"{self.filter_stats['jobs_filtered']} filtered ({filter_rate:.1f}%)")

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

        while True:
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
                logger.warning(f"[{company_slug}] No job listings found with any selector")
                break

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
                            # Job filtered out - don't fetch description
                            self.filter_stats['jobs_filtered'] += 1
                            self.filter_stats['filtered_titles'].append(job.title)
                            logger.debug(f"[{company_slug}] Filtered out: {job.title}")
                            continue

                    # STEP 3: Job passed filter - fetch full description (expensive)
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

            # Check for pagination controls (try multiple methods)
            pagination_found = False

            # Method 1: Try "Load More" or "Show More" buttons
            for selector in self.SELECTORS['pagination']['load_more_btn']:
                try:
                    load_more = await page.query_selector(selector)
                    if load_more:
                        # Check if button is visible and enabled
                        is_visible = await load_more.is_visible()
                        is_enabled = await load_more.is_enabled()

                        if is_visible and is_enabled:
                            await load_more.click()
                            await page.wait_for_timeout(1500)  # Wait for new jobs to load
                            logger.info(f"[{company_slug}] Clicked Load More using selector: {selector}")
                            pagination_found = True
                            break
                except Exception as e:
                    logger.debug(f"[{company_slug}] Load More selector '{selector}' failed: {str(e)[:50]}")
                    continue

            if pagination_found:
                continue

            # Method 2: Try "Next" button/link
            for selector in self.SELECTORS['pagination']['next_btn']:
                try:
                    next_btn = await page.query_selector(selector)
                    if next_btn:
                        # Check if Next button exists and is enabled
                        is_visible = await next_btn.is_visible()
                        is_enabled = await next_btn.is_enabled()

                        if is_visible and is_enabled:
                            await next_btn.click()
                            await page.wait_for_timeout(2000)  # Wait for page to load
                            logger.info(f"[{company_slug}] Clicked Next button using selector: {selector}")
                            pagination_found = True
                            break
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
                                    await link.click()
                                    await page.wait_for_timeout(2000)
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

            # No pagination found - we've reached the end
            logger.info(f"[{company_slug}] No more pagination controls found, scraping complete")
            break

        return jobs

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
            # Get title from the element text content (works for <a> tags)
            title = await job_element.text_content()
            title = title.strip() if title else "Unknown"

            # Get URL - try as href attribute (if it's an <a> tag)
            job_url = await job_element.get_attribute('href')

            # If no href, try to find a link inside this element
            if not job_url:
                try:
                    link = await job_element.query_selector('a')
                    if link:
                        job_url = await link.get_attribute('href')
                except:
                    pass

            if not job_url:
                logger.debug(f"[{company_slug}] No job URL found for job element")
                return None

            # Job URLs from Greenhouse are already absolute (from stripe.com/jobs/listing/...)
            # or relative paths. If relative, join with a default base URL
            if not job_url.startswith('http'):
                job_url = urljoin(self.BASE_URLS[0], job_url)

            logger.debug(f"[{company_slug}] Extracted job: {title} -> {job_url}")

            # Extract job ID from URL
            job_id_match = re.search(r'/jobs/(\d+)', job_url)
            job_id = job_id_match.group(1) if job_id_match else None

            # Try to get location from within the element
            location = "Unspecified"
            try:
                # For BEM-style structures, location might be a sibling or nearby element
                # We'll be lenient here and just get what we can
                location_elem = await job_element.query_selector('span')
                if location_elem:
                    location_text = await location_elem.text_content()
                    location = location_text.strip() if location_text else "Unspecified"
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
        company_slugs: List[str]
    ) -> Dict[str, Dict]:
        """
        Scrape multiple companies sequentially.

        Args:
            company_slugs: List of company slugs

        Returns:
            Dict mapping company_slug to dict with 'jobs' and 'stats'
        """
        results = {}

        for company_slug in company_slugs:
            results[company_slug] = await self.scrape_company(company_slug)
            await asyncio.sleep(1)  # Rate limit between companies

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
