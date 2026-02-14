"""
Workable Postings API Client

PURPOSE:
Fetch job postings from Workable's public API (no auth required).
Follows the same functional pattern as ashby_fetcher.py.

API Endpoint:
    GET https://www.workable.com/api/accounts/{subdomain}?details=true

Key Advantages:
- Structured workplace_type field (on_site/hybrid/remote) - maps directly to working_arrangement
- Structured salary data (salary_from/salary_to/salary_currency)
- Structured location (city/country_code/region)
- Unique shortcode identifier

USAGE:
    from scrapers.workable.workable_fetcher import fetch_workable_jobs, fetch_all_workable_companies

    # Fetch from single company
    jobs, stats = fetch_workable_jobs('acme')

    # Fetch from all companies in mapping
    all_jobs, combined_stats = fetch_all_workable_companies()

    # With filtering
    jobs, stats = fetch_workable_jobs('acme', filter_titles=True, filter_locations=True)
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

# Workable API endpoint
WORKABLE_API_URL = "https://www.workable.com/api/accounts"

# Rate limiting: 2 seconds between requests (Workable has aggressive rate limits)
RATE_LIMIT_DELAY = 2.0


@dataclass
class WorkableJob:
    """Parsed Workable job posting."""
    id: str                               # shortcode from API
    title: str
    company_slug: str                     # subdomain
    location: str                         # combined location string
    description: str                      # full description
    url: str                              # job URL
    apply_url: str                        # application URL
    department: Optional[str] = None
    employment_type: Optional[str] = None  # full_time, part_time, contract, etc.
    workplace_type: Optional[str] = None   # on_site, hybrid, remote - KEY FIELD
    # Structured compensation (like Ashby)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    # Structured location
    city: Optional[str] = None
    region: Optional[str] = None
    country_code: Optional[str] = None
    # Metadata
    published_at: Optional[str] = None


def parse_workable_job(job_data: Dict, company_slug: str) -> WorkableJob:
    """
    Parse raw Workable API job data into WorkableJob object.

    Args:
        job_data: Raw job dict from Workable API
        company_slug: The company's Workable subdomain

    Returns:
        WorkableJob object

    Note: API response may include both formats:
        - `workplace_type` enum (on_site/hybrid/remote) or `telecommuting` boolean
        - Location as nested object or top-level fields (city, country, state) + locations array
        - Salary may not be present in most jobs
    """
    # Extract salary components (may not be present)
    salary_data = job_data.get('salary', {}) or {}

    # Extract nested location object (API returns location as nested dict)
    location_obj = job_data.get('location', {}) or {}

    # Build location string: prefer location_str, fall back to component fields
    location_str = location_obj.get('location_str', '')
    if not location_str:
        # Build from top-level fields first, then fall back to nested location object
        location_parts = []
        city = job_data.get('city') or location_obj.get('city')
        state = job_data.get('state') or location_obj.get('region')
        country = job_data.get('country') or location_obj.get('country')
        if city:
            location_parts.append(city)
        if state:
            location_parts.append(state)
        if country:
            location_parts.append(country)
        location_str = ', '.join(location_parts)

    # Extract structured location fields (top-level first, then nested)
    city = job_data.get('city') or location_obj.get('city')
    region = job_data.get('state') or location_obj.get('region')

    # Extract country_code: locations array > nested location > None
    country_code = location_obj.get('country_code')
    if not country_code:
        locations_array = job_data.get('locations', [])
        if locations_array and isinstance(locations_array, list):
            country_code = locations_array[0].get('countryCode')

    # Map workplace_type: prefer explicit field, fall back to telecommuting boolean
    workplace_type = job_data.get('workplace_type')
    if not workplace_type:
        telecommuting = job_data.get('telecommuting', False)
        workplace_type = 'remote' if telecommuting else 'on_site'

    return WorkableJob(
        id=job_data.get('shortcode', ''),
        title=job_data.get('title', ''),
        company_slug=company_slug,
        location=location_str,
        description=job_data.get('description', ''),
        url=job_data.get('url', ''),
        apply_url=job_data.get('application_url', ''),
        department=job_data.get('department'),
        employment_type=job_data.get('employment_type'),
        workplace_type=workplace_type,
        salary_min=salary_data.get('salary_from'),
        salary_max=salary_data.get('salary_to'),
        salary_currency=salary_data.get('salary_currency'),
        city=city,
        region=region,
        country_code=country_code,
        published_at=job_data.get('published_on') or job_data.get('created_at')
    )


def fetch_workable_jobs(
    company_slug: str,
    filter_titles: bool = False,
    filter_locations: bool = False,
    title_patterns: Optional[List[str]] = None,
    location_patterns: Optional[List[str]] = None,
    rate_limit: float = RATE_LIMIT_DELAY
) -> Tuple[List[WorkableJob], Dict]:
    """
    Fetch all jobs for a single Workable company.

    Args:
        company_slug: The company's Workable subdomain (e.g., 'acme', 'stripe')
        filter_titles: Apply title filtering to remove non-target roles
        filter_locations: Apply location filtering to remove non-target cities
        title_patterns: Regex patterns for title filtering (loaded from config if None)
        location_patterns: Substring patterns for location filtering (loaded from config if None)
        rate_limit: Seconds to wait after request

    Returns:
        Tuple of (list of WorkableJob objects, stats dict)
    """
    stats = {
        'jobs_fetched': 0,
        'jobs_kept': 0,
        'filtered_by_title': 0,
        'filtered_by_location': 0,
        'error': None
    }

    url = f"{WORKABLE_API_URL}/{company_slug}"
    params = {'details': 'true'}

    headers = {
        'User-Agent': 'job-analytics-bot/1.0 (github.com/job-analytics)',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 404:
            logger.warning(f"Workable company not found: {company_slug}")
            stats['error'] = 'Company not found'
            return [], stats

        if response.status_code == 429:
            logger.warning(f"Rate limited for {company_slug}")
            stats['error'] = 'Rate limited'
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
                Path(__file__).parent.parent.parent / 'config' / 'workable' / 'title_patterns.yaml'
            )

        if filter_locations and location_patterns is None:
            from scrapers.common.filters import load_location_patterns
            location_patterns = load_location_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'workable' / 'location_patterns.yaml'
            )

        # Import filter functions
        if filter_titles or filter_locations:
            from scrapers.common.filters import is_relevant_role, matches_target_location

        # Parse and filter jobs
        jobs = []
        for job_data in jobs_data:
            title = job_data.get('title', '')

            # Build location string for filtering (actual API uses top-level fields)
            location_parts = []
            if job_data.get('city'):
                location_parts.append(job_data['city'])
            if job_data.get('state'):
                location_parts.append(job_data['state'])
            if job_data.get('country'):
                location_parts.append(job_data['country'])
            location_str = ', '.join(location_parts)

            # Apply title filter
            if filter_titles and title_patterns:
                if not is_relevant_role(title, title_patterns):
                    stats['filtered_by_title'] += 1
                    continue

            # Apply location filter
            if filter_locations and location_patterns:
                # Check location string
                location_matched = matches_target_location(location_str, location_patterns)

                if not location_matched:
                    stats['filtered_by_location'] += 1
                    continue

            job = parse_workable_job(job_data, company_slug)
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
        mapping_path: Path to workable/company_mapping.json

    Returns:
        Dict with 'workable' key containing company data
    """
    if mapping_path is None:
        mapping_path = Path(__file__).parent.parent.parent / 'config' / 'workable' / 'company_mapping.json'

    if not mapping_path.exists():
        logger.warning(f"Company mapping not found: {mapping_path}")
        return {'workable': {}}

    with open(mapping_path) as f:
        return json.load(f)


def fetch_all_workable_companies(
    companies: Optional[List[str]] = None,
    filter_titles: bool = True,
    filter_locations: bool = True,
    rate_limit: float = RATE_LIMIT_DELAY,
    on_company_complete: Optional[callable] = None
) -> Tuple[List[WorkableJob], Dict]:
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
    workable_companies = mapping.get('workable', {})

    if not workable_companies:
        logger.warning("No companies in Workable mapping")
        return [], combined_stats

    # Filter to specified companies if provided
    if companies:
        companies_to_process = {
            name: data for name, data in workable_companies.items()
            if data.get('slug') in companies
        }
    else:
        companies_to_process = workable_companies

    # Load filter patterns once
    title_patterns = None
    location_patterns = None

    if filter_titles:
        try:
            from scrapers.common.filters import load_title_patterns
            title_patterns = load_title_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'workable' / 'title_patterns.yaml'
            )
        except Exception as e:
            logger.warning(f"Could not load title patterns: {e}")

    if filter_locations:
        try:
            from scrapers.common.filters import load_location_patterns
            location_patterns = load_location_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'workable' / 'location_patterns.yaml'
            )
        except Exception as e:
            logger.warning(f"Could not load location patterns: {e}")

    logger.info(f"Fetching from {len(companies_to_process)} Workable companies...")

    for company_name, company_data in companies_to_process.items():
        slug = company_data.get('slug', '')
        if not slug:
            logger.warning(f"No slug for company: {company_name}")
            continue

        logger.info(f"  Fetching: {company_name} ({slug})")

        jobs, stats = fetch_workable_jobs(
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
    Quick check if a company uses Workable.

    Args:
        slug: Company subdomain to check

    Returns:
        True if company exists on Workable, False otherwise
    """
    try:
        response = requests.get(
            f"{WORKABLE_API_URL}/{slug}",
            timeout=10
        )
        return response.status_code == 200
    except:
        return False


# Standalone test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Fetch jobs from Workable API')
    parser.add_argument('--slug', type=str, help='Single company slug to test')
    parser.add_argument('--all', action='store_true', help='Fetch from all companies in mapping')
    parser.add_argument('--no-filter', action='store_true', help='Disable title/location filtering')
    parser.add_argument('--check', type=str, help='Check if company slug exists on Workable')
    args = parser.parse_args()

    if args.check:
        exists = check_company_exists(args.check)
        print(f"Company '{args.check}' exists on Workable: {exists}")

    elif args.slug:
        # Test single company
        jobs, stats = fetch_workable_jobs(
            args.slug,
            filter_titles=not args.no_filter,
            filter_locations=not args.no_filter
        )
        print(f"\nFetched {len(jobs)} jobs from {args.slug}")
        for job in jobs[:5]:
            print(f"  - {job.title} ({job.location})")
            print(f"    Workplace: {job.workplace_type}")
            print(f"    Salary: {job.salary_min}-{job.salary_max} {job.salary_currency}")
            print(f"    Description: {len(job.description)} chars")
        print(f"\nStats: {json.dumps(stats, indent=2)}")

    elif args.all:
        # Fetch from all companies
        jobs, stats = fetch_all_workable_companies(
            filter_titles=not args.no_filter,
            filter_locations=not args.no_filter
        )
        print(f"\nTotal: {len(jobs)} jobs")
        print(f"Stats: {json.dumps(stats, indent=2)}")

    else:
        # Quick connectivity test
        print("Testing Workable API connectivity...")
        print("Use --slug <subdomain> to test a specific company")
        print("Use --check <subdomain> to verify a company exists")
