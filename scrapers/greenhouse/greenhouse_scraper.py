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
    BASE_URLS = [
        "https://job-boards.greenhouse.io",  # New domain (try first)
        "https://boards.greenhouse.io",      # Legacy domain (fallback)
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
        'load_more_btn': 'button:has-text("Load More")',

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

    def __init__(self, headless: bool = True, timeout_ms: int = 30000, max_concurrent_pages: int = 2):
        """
        Initialize scraper.

        Args:
            headless: Run browser in headless mode (no UI)
            timeout_ms: Timeout for page operations in milliseconds
            max_concurrent_pages: Max number of concurrent pages to prevent browser crashes
        """
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.max_concurrent_pages = max_concurrent_pages
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.active_pages = 0

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
        max_retries: int = 3
    ) -> List[Job]:
        """
        Scrape all jobs for a single company.

        Args:
            company_slug: Company slug for Greenhouse URL (e.g., 'stripe')
            max_retries: Number of retries on failure

        Returns:
            List of Job objects
        """
        if not self.context:
            raise RuntimeError("Scraper not initialized. Call .init() first.")

        page = None

        # Try each base URL until one works
        for base_url in self.BASE_URLS:
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

                        # Extract jobs
                        jobs = await self._extract_all_jobs(page, company_slug)
                        logger.info(f"[{company_slug}] Successfully scraped {len(jobs)} jobs from {base_url}")
                        return jobs

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
        return []

    async def _extract_all_jobs(self, page: Page, company_slug: str) -> List[Job]:
        """Extract all jobs from listing page, handling pagination."""
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
                    job = await self._extract_job_listing(job_element, company_slug, page)
                    if job and job.url not in seen_urls:
                        jobs.append(job)
                        seen_urls.add(job.url)
                except Exception as e:
                    logger.warning(f"[{company_slug}] Failed to extract job: {str(e)[:100]}")
                    continue

            # Check for "Load More" button
            try:
                load_more = await page.query_selector(self.SELECTORS['load_more_btn'])
                if load_more:
                    await load_more.click()
                    await page.wait_for_timeout(1000)
                    logger.info(f"[{company_slug}] Clicked Load More, waiting for new jobs...")
                    continue
            except:
                pass

            break  # No more jobs to load

        return jobs

    async def _extract_job_listing(
        self,
        job_element,
        company_slug: str,
        page: Page
    ) -> Optional[Job]:
        """Extract a single job from listing element."""
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

            # Get full description from job detail page
            # Uses page pooling to prevent browser crashes
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
    ) -> Dict[str, List[Job]]:
        """
        Scrape multiple companies sequentially.

        Args:
            company_slugs: List of company slugs

        Returns:
            Dict mapping company_slug to list of jobs
        """
        results = {}

        for company_slug in company_slugs:
            results[company_slug] = await self.scrape_company(company_slug)
            await asyncio.sleep(1)  # Rate limit between companies

        return results


async def main():
    """Example usage"""

    test_companies = [
        'stripe',
        'figma',
        'github',
    ]

    scraper = GreenhouseScraper(headless=True)

    try:
        await scraper.init()
        results = await scraper.scrape_all(test_companies)

        # Print results
        for company, jobs in results.items():
            print(f"\n{'='*70}")
            print(f"{company.upper()}: {len(jobs)} jobs found")
            print('='*70)

            for i, job in enumerate(jobs[:2], 1):  # Show first 2
                print(f"\n[{i}] {job.title}")
                print(f"    Location: {job.location}")
                print(f"    Department: {job.department}")
                print(f"    Description (first 300 chars): {job.description[:300]}...")

        # Save to JSON for verification
        output = {
            company: [asdict(j) for j in jobs]
            for company, jobs in results.items()
        }

        with open('greenhouse_scrape_results.json', 'w') as f:
            json.dump(output, f, indent=2, default=str)

        print("\n\nResults saved to greenhouse_scrape_results.json")

    finally:
        await scraper.close()


if __name__ == '__main__':
    asyncio.run(main())
