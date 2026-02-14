"""
Greenhouse Job Board API Client

PURPOSE:
Fetch job postings from Greenhouse's public Job Board API (no auth required).
Replaces the Playwright-based browser automation scraper with a simple REST API
client, following the same pattern as ashby_fetcher.py.

API Endpoint:
    GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true

Key Advantages over Playwright scraper:
- Single HTTP request per company (vs browser launch + page navigation)
- Structured salary data (pay_input_ranges with min/max cents)
- Department and office data in dedicated fields
- updated_at timestamp for change detection
- ~30x faster per company (~1-2s vs ~47s)
- No browser dependency

USAGE:
    from scrapers.greenhouse.greenhouse_api_fetcher import (
        fetch_greenhouse_jobs, load_company_mapping, GreenhouseJob
    )

    # Fetch from single company
    jobs, stats = fetch_greenhouse_jobs('figma')

    # With filtering
    jobs, stats = fetch_greenhouse_jobs('figma', filter_titles=True, filter_locations=True)
"""

import sys
import json
import time
import logging
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Greenhouse Job Board API endpoint
GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards"

# Rate limiting: lighter than Playwright since API is heavily cached
RATE_LIMIT_DELAY = 0.5


@dataclass
class GreenhouseJob:
    """Parsed Greenhouse job posting from the Job Board API."""
    id: str
    title: str
    company_slug: str
    location: str
    description: str
    url: str
    department: Optional[str] = None
    updated_at: Optional[str] = None
    # Structured compensation (from pay_input_ranges)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None


def parse_compensation(pay_ranges: Optional[List[Dict]]) -> Dict:
    """
    Extract salary from Greenhouse pay_input_ranges.

    Greenhouse provides compensation in cents with currency_type.
    We convert cents to whole dollars/pounds.

    Args:
        pay_ranges: List of pay range dicts from API response

    Returns:
        Dict with keys: min, max, currency
    """
    if not pay_ranges:
        return {}

    result = {}

    # Use first pay range (primary compensation)
    pay_range = pay_ranges[0]

    min_cents = pay_range.get('min_cents')
    max_cents = pay_range.get('max_cents')
    currency = pay_range.get('currency_type')

    if min_cents is not None:
        result['min'] = min_cents // 100
    if max_cents is not None:
        result['max'] = max_cents // 100
    if currency:
        result['currency'] = currency

    return result


def parse_greenhouse_job(job_data: Dict, company_slug: str) -> GreenhouseJob:
    """
    Parse raw Greenhouse API job data into GreenhouseJob object.

    Converts HTML content field to plain text using strip_html().

    Args:
        job_data: Raw job dict from Greenhouse API
        company_slug: The company's Greenhouse board token

    Returns:
        GreenhouseJob object
    """
    from scrapers.common.filters import strip_html

    # Extract location
    location_data = job_data.get('location', {})
    location = location_data.get('name', '') if isinstance(location_data, dict) else str(location_data)

    # Extract department (first department if multiple)
    departments = job_data.get('departments', [])
    department = departments[0].get('name') if departments else None

    # Parse compensation
    comp = parse_compensation(job_data.get('pay_input_ranges'))

    # Convert HTML content to plain text
    content_html = job_data.get('content', '')
    description = strip_html(content_html) if content_html else ''

    return GreenhouseJob(
        id=str(job_data.get('id', '')),
        title=job_data.get('title', ''),
        company_slug=company_slug,
        location=location,
        description=description,
        url=job_data.get('absolute_url', ''),
        department=department,
        updated_at=job_data.get('updated_at'),
        salary_min=comp.get('min'),
        salary_max=comp.get('max'),
        salary_currency=comp.get('currency'),
    )


def fetch_greenhouse_jobs(
    board_token: str,
    filter_titles: bool = False,
    filter_locations: bool = False,
    title_patterns: Optional[List[str]] = None,
    location_patterns: Optional[List[str]] = None,
    rate_limit: float = RATE_LIMIT_DELAY
) -> Tuple[List[GreenhouseJob], Dict]:
    """
    Fetch all jobs for a single Greenhouse company via the Job Board API.

    Single request per company with ?content=true to inline full descriptions.

    Args:
        board_token: The company's Greenhouse board token/slug
        filter_titles: Apply title filtering to remove non-target roles
        filter_locations: Apply location filtering to remove non-target cities
        title_patterns: Regex patterns for title filtering (loaded from config if None)
        location_patterns: Substring patterns for location filtering (loaded from config if None)
        rate_limit: Seconds to wait after request

    Returns:
        Tuple of (list of GreenhouseJob objects, stats dict)
    """
    stats = {
        'jobs_fetched': 0,
        'jobs_kept': 0,
        'filtered_by_title': 0,
        'filtered_by_location': 0,
        'error': None
    }

    url = f"{GREENHOUSE_API_URL}/{board_token}/jobs"
    params = {'content': 'true'}

    headers = {
        'User-Agent': 'job-analytics-bot/1.0 (github.com/job-analytics)',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 404:
            logger.warning(f"Greenhouse board not found: {board_token}")
            stats['error'] = 'Board not found'
            return [], stats

        response.raise_for_status()
        data = response.json()

        jobs_data = data.get('jobs', [])
        if not isinstance(jobs_data, list):
            logger.warning(f"Unexpected response format from {board_token}")
            stats['error'] = 'Invalid response format'
            return [], stats

        stats['jobs_fetched'] = len(jobs_data)

        # Load filter patterns if filtering enabled
        if filter_titles and title_patterns is None:
            from scrapers.common.filters import load_title_patterns
            title_patterns = load_title_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'title_patterns.yaml'
            )

        if filter_locations and location_patterns is None:
            from scrapers.common.filters import load_location_patterns
            location_patterns = load_location_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'location_patterns.yaml'
            )

        # Import filter functions
        if filter_titles or filter_locations:
            from scrapers.common.filters import is_relevant_role, matches_target_location

        # Parse and filter jobs
        jobs = []
        for job_data in jobs_data:
            title = job_data.get('title', '')

            # Build location string for filtering
            location_data = job_data.get('location', {})
            location = location_data.get('name', '') if isinstance(location_data, dict) else str(location_data)

            # Apply title filter
            if filter_titles and title_patterns:
                if not is_relevant_role(title, title_patterns):
                    stats['filtered_by_title'] += 1
                    continue

            # Apply location filter (location.name field only)
            if filter_locations and location_patterns:
                if not matches_target_location(location, location_patterns):
                    stats['filtered_by_location'] += 1
                    continue

            job = parse_greenhouse_job(job_data, board_token)
            jobs.append(job)

        stats['jobs_kept'] = len(jobs)

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching from {board_token}")
        stats['error'] = 'Timeout'
        return [], stats

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for {board_token}: {e}")
        stats['error'] = str(e)[:100]
        return [], stats

    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from {board_token}")
        stats['error'] = 'Invalid JSON'
        return [], stats

    finally:
        # Rate limit
        time.sleep(rate_limit)

    return jobs, stats


def load_company_mapping(mapping_path: Optional[Path] = None) -> Dict:
    """
    Load company mapping from config file.

    Args:
        mapping_path: Path to greenhouse/company_ats_mapping.json

    Returns:
        Dict with 'greenhouse' key containing company data
    """
    if mapping_path is None:
        mapping_path = Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'company_ats_mapping.json'

    if not mapping_path.exists():
        logger.warning(f"Company mapping not found: {mapping_path}")
        return {'greenhouse': {}}

    with open(mapping_path) as f:
        return json.load(f)


def fetch_all_greenhouse_companies(
    companies: Optional[List[str]] = None,
    filter_titles: bool = True,
    filter_locations: bool = True,
    rate_limit: float = RATE_LIMIT_DELAY,
    on_company_complete: Optional[callable] = None
) -> Tuple[List[GreenhouseJob], Dict]:
    """
    Fetch jobs from all companies in mapping (or specified list).

    Args:
        companies: Optional list of company slugs to fetch. If None, uses mapping.
        filter_titles: Apply title filtering
        filter_locations: Apply location filtering
        rate_limit: Seconds between requests
        on_company_complete: Optional callback(slug, jobs, stats) after each company

    Returns:
        Tuple of (all jobs, combined stats)
    """
    all_jobs = []
    combined_stats = {
        'companies_processed': 0,
        'companies_with_jobs': 0,
        'total_jobs_fetched': 0,
        'total_jobs_kept': 0,
        'total_filtered_by_title': 0,
        'total_filtered_by_location': 0,
        'errors': []
    }

    # Load mapping
    mapping = load_company_mapping()
    gh_companies = mapping.get('greenhouse', {})

    if not gh_companies:
        logger.warning("No companies in Greenhouse mapping")
        return [], combined_stats

    # Filter to specified companies if provided
    if companies:
        companies_to_process = {
            name: data for name, data in gh_companies.items()
            if data['slug'] in companies
        }
    else:
        companies_to_process = gh_companies

    # Load filter patterns once
    title_patterns = None
    location_patterns = None

    if filter_titles:
        try:
            from scrapers.common.filters import load_title_patterns
            title_patterns = load_title_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'title_patterns.yaml'
            )
        except Exception as e:
            logger.warning(f"Could not load title patterns: {e}")

    if filter_locations:
        try:
            from scrapers.common.filters import load_location_patterns
            location_patterns = load_location_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'location_patterns.yaml'
            )
        except Exception as e:
            logger.warning(f"Could not load location patterns: {e}")

    logger.info(f"Fetching from {len(companies_to_process)} Greenhouse companies...")

    for company_name, company_data in companies_to_process.items():
        slug = company_data['slug']

        logger.info(f"  Fetching: {company_name} ({slug})")

        jobs, stats = fetch_greenhouse_jobs(
            board_token=slug,
            filter_titles=filter_titles,
            filter_locations=filter_locations,
            title_patterns=title_patterns,
            location_patterns=location_patterns,
            rate_limit=rate_limit
        )

        combined_stats['companies_processed'] += 1
        combined_stats['total_jobs_fetched'] += stats['jobs_fetched']
        combined_stats['total_jobs_kept'] += stats['jobs_kept']
        combined_stats['total_filtered_by_title'] += stats['filtered_by_title']
        combined_stats['total_filtered_by_location'] += stats['filtered_by_location']

        if jobs:
            combined_stats['companies_with_jobs'] += 1
            all_jobs.extend(jobs)

        if stats['error']:
            combined_stats['errors'].append(f"{slug}: {stats['error']}")

        if on_company_complete:
            on_company_complete(slug, jobs, stats)

        # Progress logging
        logger.info(
            f"    {stats['jobs_fetched']} fetched, {stats['jobs_kept']} kept "
            f"(title: -{stats['filtered_by_title']}, loc: -{stats['filtered_by_location']})"
        )

    logger.info(f"Total: {len(all_jobs)} jobs from {combined_stats['companies_with_jobs']} companies")

    return all_jobs, combined_stats


# Standalone test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Fetch jobs from Greenhouse API')
    parser.add_argument('--slug', type=str, help='Single company slug to test')
    parser.add_argument('--all', action='store_true', help='Fetch from all companies in mapping')
    parser.add_argument('--no-filter', action='store_true', help='Disable title/location filtering')
    args = parser.parse_args()

    if args.slug:
        # Test single company
        jobs, stats = fetch_greenhouse_jobs(
            args.slug,
            filter_titles=not args.no_filter,
            filter_locations=not args.no_filter
        )
        print(f"\nFetched {len(jobs)} jobs from {args.slug}")
        for job in jobs[:5]:
            print(f"  - {job.title} ({job.location})")
            print(f"    Salary: {job.salary_min}-{job.salary_max} {job.salary_currency}")
            print(f"    Department: {job.department}")
            print(f"    Description: {len(job.description)} chars")
        print(f"\nStats: {json.dumps(stats, indent=2)}")

    elif args.all:
        # Fetch from all companies
        jobs, stats = fetch_all_greenhouse_companies(
            filter_titles=not args.no_filter,
            filter_locations=not args.no_filter
        )
        print(f"\nTotal: {len(jobs)} jobs")
        print(f"Stats: {json.dumps(stats, indent=2)}")

    else:
        # Quick test with Figma
        print("Testing with Figma...")
        jobs, stats = fetch_greenhouse_jobs('figma', filter_titles=False, filter_locations=False)
        print(f"Fetched {len(jobs)} jobs")
        if jobs:
            job = jobs[0]
            print(f"\nSample job:")
            print(f"  Title: {job.title}")
            print(f"  Location: {job.location}")
            print(f"  Department: {job.department}")
            print(f"  Salary: {job.salary_min}-{job.salary_max} {job.salary_currency}")
            print(f"  URL: {job.url}")
            print(f"  Description length: {len(job.description)} chars")
            print(f"  Description preview: {job.description[:300]}...")
