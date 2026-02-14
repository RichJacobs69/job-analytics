"""
Ashby Postings API Client

PURPOSE:
Fetch job postings from Ashby's public API (no auth required).
Follows the same functional pattern as lever_fetcher.py.

API Endpoint:
    GET https://api.ashbyhq.com/posting-api/job-board/{company_slug}?includeCompensation=true

Key Advantages:
- Structured compensation data (min/max/currency in dedicated fields)
- Explicit isRemote boolean flag
- Structured postalAddress (city/region/country)
- Both HTML and plain text descriptions provided
- Published date in ISO 8601 format

USAGE:
    from scrapers.ashby.ashby_fetcher import fetch_ashby_jobs, fetch_all_ashby_companies

    # Fetch from single company
    jobs, stats = fetch_ashby_jobs('notion')

    # Fetch from all companies in mapping
    all_jobs, combined_stats = fetch_all_ashby_companies()

    # With filtering
    jobs, stats = fetch_ashby_jobs('notion', filter_titles=True, filter_locations=True)
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

# Ashby API endpoint
ASHBY_API_URL = "https://api.ashbyhq.com/posting-api/job-board"

# Rate limiting: 1 request per second (conservative)
RATE_LIMIT_DELAY = 1.0


@dataclass
class AshbyJob:
    """Parsed Ashby job posting."""
    id: str
    title: str
    company_slug: str
    location: str
    description: str
    url: str
    apply_url: str
    department: Optional[str] = None
    team: Optional[str] = None
    employment_type: Optional[str] = None  # FullTime, PartTime, Contract, etc.
    is_remote: bool = False
    # Structured compensation (Ashby's key advantage)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    compensation_summary: Optional[str] = None
    # Structured location
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    # Metadata
    published_at: Optional[str] = None


def parse_compensation(comp_data: Optional[Dict]) -> Dict:
    """
    Extract structured compensation from Ashby's nested format.

    Ashby provides compensation in multiple formats:
    1. salaryRange in compensationTiers (some companies)
    2. components array within tiers with compensationType='Salary' (Ramp, etc.)
    3. summaryComponents at top level

    Args:
        comp_data: Raw compensation dict from Ashby API

    Returns:
        Dict with keys: min, max, currency, summary
    """
    if not comp_data:
        return {}

    result = {
        'summary': comp_data.get('compensationTierSummary')
    }

    # Method 1: Try salaryRange in compensationTiers (original approach)
    tiers = comp_data.get('compensationTiers', [])
    if tiers:
        tier = tiers[0]
        salary_range = tier.get('salaryRange', {})

        if salary_range:
            min_data = salary_range.get('min', {})
            max_data = salary_range.get('max', {})

            if min_data.get('value'):
                result['min'] = int(min_data['value'])
                result['currency'] = min_data.get('currency')

            if max_data.get('value'):
                result['max'] = int(max_data['value'])
                result['currency'] = max_data.get('currency', result.get('currency'))

        # Method 2: Try components array within tier (Ramp pattern)
        if 'min' not in result:
            components = tier.get('components', [])
            for comp in components:
                if comp.get('compensationType') == 'Salary':
                    min_val = comp.get('minValue')
                    max_val = comp.get('maxValue')
                    currency = comp.get('currencyCode')

                    if min_val:
                        result['min'] = int(min_val)
                    if max_val:
                        result['max'] = int(max_val)
                    if currency:
                        result['currency'] = currency
                    break

    # Method 3: Try summaryComponents at top level (fallback)
    if 'min' not in result:
        summary_components = comp_data.get('summaryComponents', [])
        for comp in summary_components:
            if comp.get('compensationType') == 'Salary':
                min_val = comp.get('minValue')
                max_val = comp.get('maxValue')
                currency = comp.get('currencyCode')

                if min_val:
                    result['min'] = int(min_val)
                if max_val:
                    result['max'] = int(max_val)
                if currency:
                    result['currency'] = currency
                break

    return result


def parse_ashby_job(job_data: Dict, company_slug: str) -> AshbyJob:
    """
    Parse raw Ashby API job data into AshbyJob object.

    Args:
        job_data: Raw job dict from Ashby API
        company_slug: The company's Ashby site slug

    Returns:
        AshbyJob object
    """
    # Extract structured address if available
    address_data = job_data.get('address') or {}
    address = address_data.get('postalAddress') or {}

    # Handle secondary locations (some jobs have multiple)
    location_parts = []
    primary_location = job_data.get('location', '')
    if primary_location:
        location_parts.append(primary_location)

    secondary_locs = job_data.get('secondaryLocations', [])
    for sec_loc in secondary_locs:
        sec_location = sec_loc.get('location', '')
        if sec_location and sec_location not in location_parts:
            location_parts.append(sec_location)

    combined_location = ' / '.join(location_parts) if location_parts else ''

    # Parse compensation
    comp = parse_compensation(job_data.get('compensation'))

    # Map employment type to our format
    employment_type = job_data.get('employmentType', '')

    return AshbyJob(
        id=job_data.get('id', ''),
        title=job_data.get('title', ''),
        company_slug=company_slug,
        location=combined_location,
        description=job_data.get('descriptionPlain', '') or job_data.get('descriptionHtml', ''),
        url=job_data.get('jobUrl', ''),
        apply_url=job_data.get('applyUrl', ''),
        department=job_data.get('department'),
        team=job_data.get('team'),
        employment_type=employment_type,
        is_remote=job_data.get('isRemote', False),
        salary_min=comp.get('min'),
        salary_max=comp.get('max'),
        salary_currency=comp.get('currency'),
        compensation_summary=comp.get('summary'),
        city=address.get('addressLocality'),
        region=address.get('addressRegion'),
        country=address.get('addressCountry'),
        published_at=job_data.get('publishedAt')
    )


def fetch_ashby_jobs(
    company_slug: str,
    filter_titles: bool = False,
    filter_locations: bool = False,
    title_patterns: Optional[List[str]] = None,
    location_patterns: Optional[List[str]] = None,
    rate_limit: float = RATE_LIMIT_DELAY
) -> Tuple[List[AshbyJob], Dict]:
    """
    Fetch all jobs for a single Ashby company.

    Args:
        company_slug: The company's Ashby site slug (e.g., 'notion', 'anthropic')
        filter_titles: Apply title filtering to remove non-target roles
        filter_locations: Apply location filtering to remove non-target cities
        title_patterns: Regex patterns for title filtering (loaded from config if None)
        location_patterns: Substring patterns for location filtering (loaded from config if None)
        rate_limit: Seconds to wait after request

    Returns:
        Tuple of (list of AshbyJob objects, stats dict)
    """
    stats = {
        'jobs_fetched': 0,
        'jobs_kept': 0,
        'filtered_by_title': 0,
        'filtered_by_location': 0,
        'error': None
    }

    url = f"{ASHBY_API_URL}/{company_slug}"
    params = {'includeCompensation': 'true'}

    headers = {
        'User-Agent': 'job-analytics-bot/1.0 (github.com/job-analytics)',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 404:
            logger.warning(f"Ashby company not found: {company_slug}")
            stats['error'] = 'Company not found'
            return [], stats

        response.raise_for_status()
        data = response.json()

        jobs_data = data.get('jobs', [])
        if not isinstance(jobs_data, list):
            logger.warning(f"Unexpected response format from {company_slug}")
            stats['error'] = 'Invalid response format'
            return [], stats

        stats['jobs_fetched'] = len(jobs_data)

        # Load filter patterns if filtering enabled
        if filter_titles and title_patterns is None:
            from scrapers.common.filters import load_title_patterns
            title_patterns = load_title_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'ashby' / 'title_patterns.yaml'
            )

        if filter_locations and location_patterns is None:
            from scrapers.common.filters import load_location_patterns
            location_patterns = load_location_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'ashby' / 'location_patterns.yaml'
            )

        # Import filter functions
        if filter_titles or filter_locations:
            from scrapers.common.filters import is_relevant_role, matches_target_location

        # Parse and filter jobs
        jobs = []
        for job_data in jobs_data:
            title = job_data.get('title', '')

            # Build location string for filtering
            location = job_data.get('location', '')
            secondary_locs = job_data.get('secondaryLocations', [])
            all_locations = [location] if location else []
            for sec in secondary_locs:
                sec_loc = sec.get('location', '')
                if sec_loc:
                    all_locations.append(sec_loc)
            location_str = ' / '.join(all_locations)

            # Apply title filter
            if filter_titles and title_patterns:
                if not is_relevant_role(title, title_patterns):
                    stats['filtered_by_title'] += 1
                    continue

            # Apply location filter (location field only)
            if filter_locations and location_patterns:
                if not matches_target_location(location_str, location_patterns):
                    stats['filtered_by_location'] += 1
                    continue

            job = parse_ashby_job(job_data, company_slug)
            jobs.append(job)

        stats['jobs_kept'] = len(jobs)

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching from {company_slug}")
        stats['error'] = 'Timeout'
        return [], stats

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for {company_slug}: {e}")
        stats['error'] = str(e)[:100]
        return [], stats

    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from {company_slug}")
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
        mapping_path: Path to ashby/company_mapping.json

    Returns:
        Dict with 'ashby' key containing company data
    """
    if mapping_path is None:
        mapping_path = Path(__file__).parent.parent.parent / 'config' / 'ashby' / 'company_mapping.json'

    if not mapping_path.exists():
        logger.warning(f"Company mapping not found: {mapping_path}")
        return {'ashby': {}}

    with open(mapping_path) as f:
        return json.load(f)


def fetch_all_ashby_companies(
    companies: Optional[List[str]] = None,
    filter_titles: bool = True,
    filter_locations: bool = True,
    rate_limit: float = RATE_LIMIT_DELAY,
    on_company_complete: Optional[callable] = None
) -> Tuple[List[AshbyJob], Dict]:
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
    ashby_companies = mapping.get('ashby', {})

    if not ashby_companies:
        logger.warning("No companies in Ashby mapping")
        return [], combined_stats

    # Filter to specified companies if provided
    if companies:
        companies_to_process = {
            name: data for name, data in ashby_companies.items()
            if data['slug'] in companies
        }
    else:
        companies_to_process = ashby_companies

    # Load filter patterns once
    title_patterns = None
    location_patterns = None

    if filter_titles:
        try:
            from scrapers.common.filters import load_title_patterns
            title_patterns = load_title_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'ashby' / 'title_patterns.yaml'
            )
        except Exception as e:
            logger.warning(f"Could not load title patterns: {e}")

    if filter_locations:
        try:
            from scrapers.common.filters import load_location_patterns
            location_patterns = load_location_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'ashby' / 'location_patterns.yaml'
            )
        except Exception as e:
            logger.warning(f"Could not load location patterns: {e}")

    logger.info(f"Fetching from {len(companies_to_process)} Ashby companies...")

    for company_name, company_data in companies_to_process.items():
        slug = company_data['slug']

        logger.info(f"  Fetching: {company_name} ({slug})")

        jobs, stats = fetch_ashby_jobs(
            company_slug=slug,
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


def check_company_exists(slug: str) -> bool:
    """
    Quick check if a company uses Ashby.

    Args:
        slug: Company slug to check

    Returns:
        True if company exists on Ashby, False otherwise
    """
    try:
        response = requests.get(
            f"{ASHBY_API_URL}/{slug}",
            timeout=10
        )
        return response.status_code == 200
    except:
        return False


# Standalone test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Fetch jobs from Ashby API')
    parser.add_argument('--slug', type=str, help='Single company slug to test')
    parser.add_argument('--all', action='store_true', help='Fetch from all companies in mapping')
    parser.add_argument('--no-filter', action='store_true', help='Disable title/location filtering')
    parser.add_argument('--check', type=str, help='Check if company slug exists on Ashby')
    args = parser.parse_args()

    if args.check:
        exists = check_company_exists(args.check)
        print(f"Company '{args.check}' exists on Ashby: {exists}")

    elif args.slug:
        # Test single company
        jobs, stats = fetch_ashby_jobs(
            args.slug,
            filter_titles=not args.no_filter,
            filter_locations=not args.no_filter
        )
        print(f"\nFetched {len(jobs)} jobs from {args.slug}")
        for job in jobs[:5]:
            print(f"  - {job.title} ({job.location})")
            print(f"    Salary: {job.salary_min}-{job.salary_max} {job.salary_currency}")
            print(f"    Remote: {job.is_remote}")
            print(f"    Description: {len(job.description)} chars")
        print(f"\nStats: {json.dumps(stats, indent=2)}")

    elif args.all:
        # Fetch from all companies
        jobs, stats = fetch_all_ashby_companies(
            filter_titles=not args.no_filter,
            filter_locations=not args.no_filter
        )
        print(f"\nTotal: {len(jobs)} jobs")
        print(f"Stats: {json.dumps(stats, indent=2)}")

    else:
        # Quick test with Notion
        print("Testing with Notion...")
        jobs, stats = fetch_ashby_jobs('notion', filter_titles=False, filter_locations=False)
        print(f"Fetched {len(jobs)} jobs")
        if jobs:
            job = jobs[0]
            print(f"\nSample job:")
            print(f"  Title: {job.title}")
            print(f"  Location: {job.location}")
            print(f"  Remote: {job.is_remote}")
            print(f"  Salary: {job.salary_min}-{job.salary_max} {job.salary_currency}")
            print(f"  URL: {job.url}")
            print(f"  Description length: {len(job.description)} chars")
            print(f"  Description preview: {job.description[:300]}...")
