"""
SmartRecruiters Posting API Client

PURPOSE:
Fetch job postings from SmartRecruiters' public Posting API (no auth required).
Follows the same functional pattern as workable_fetcher.py.

API Endpoint:
    GET https://api.smartrecruiters.com/v1/companies/{slug}/postings

Key Advantages:
- Structured locationType field (REMOTE/ONSITE) - maps to working_arrangement
- Structured experienceLevel field - passed as classifier hint
- Pagination via offset + limit (max 100 per page)
- Rich metadata: department, industry, function
- No authentication required

USAGE:
    from scrapers.smartrecruiters.smartrecruiters_fetcher import fetch_smartrecruiters_jobs, fetch_all_smartrecruiters_companies

    # Fetch from single company
    jobs, stats = fetch_smartrecruiters_jobs('visa')

    # Fetch from all companies in mapping
    all_jobs, combined_stats = fetch_all_smartrecruiters_companies()

    # With filtering
    jobs, stats = fetch_smartrecruiters_jobs('visa', filter_titles=True, filter_locations=True)
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

# SmartRecruiters API endpoint
SMARTRECRUITERS_API_URL = "https://api.smartrecruiters.com/v1/companies"

# Rate limiting: 2 seconds between requests (conservative; no documented limit)
RATE_LIMIT_DELAY = 2.0

# Pagination limit (API max is 100)
PAGE_LIMIT = 100


@dataclass
class SmartRecruitersJob:
    """Parsed SmartRecruiters job posting."""
    id: str                                # UUID from API
    title: str
    company_slug: str                      # company identifier
    location: str                          # combined location string
    description: str                       # description from jobAd.sections
    url: str                               # job URL
    apply_url: str                         # application URL
    department: Optional[str] = None
    employment_type: Optional[str] = None  # full_time, part_time, contractor, etc.
    location_type: Optional[str] = None    # remote, onsite - KEY FIELD
    experience_level: Optional[str] = None # entry, mid_senior, director, executive, etc.
    industry: Optional[str] = None
    function: Optional[str] = None         # job function category
    # Structured location
    city: Optional[str] = None
    region: Optional[str] = None
    country_code: Optional[str] = None
    # Metadata
    published_at: Optional[str] = None


def parse_smartrecruiters_job(job_data: Dict, company_slug: str) -> SmartRecruitersJob:
    """
    Parse raw SmartRecruiters API job data into SmartRecruitersJob object.

    Args:
        job_data: Raw job dict from SmartRecruiters API
        company_slug: The company's SmartRecruiters identifier

    Returns:
        SmartRecruitersJob object

    API Response Structure (detail endpoint):
        - id: UUID string
        - name: job title
        - location: {city, region, country, remote}
        - department: {id, label}
        - experienceLevel: {id, label}
        - typeOfEmployment: {id, label}
        - industry: {id, label}
        - function: {id, label}
        - jobAd: {sections: {companyDescription, jobDescription, qualifications, additionalInformation}}
        - releasedDate: ISO timestamp
        - applyUrl: application URL
        - compensation: salary data (if available)

    Note: The list endpoint does NOT include jobAd. Description must be
    fetched from the detail endpoint (ref URL) separately.
    """
    # Build location string from nested location object
    loc = job_data.get('location', {}) or {}
    location_parts = []
    if loc.get('city'):
        location_parts.append(loc['city'])
    if loc.get('region'):
        location_parts.append(loc['region'])
    if loc.get('country'):
        location_parts.append(loc['country'])
    location_str = ', '.join(location_parts)

    # Extract description from jobAd sections
    description_parts = []
    job_ad = job_data.get('jobAd', {}) or {}
    sections = job_ad.get('sections', {}) or {}
    for section_key in ['jobDescription', 'qualifications', 'additionalInformation', 'companyDescription']:
        section = sections.get(section_key, {}) or {}
        text = section.get('text', '')
        if text:
            description_parts.append(text)
    description = '\n\n'.join(description_parts)

    # Map locationType: remote boolean in location object
    is_remote = loc.get('remote', False)
    location_type = 'remote' if is_remote else 'onsite'

    # Extract structured fields from nested objects
    dept = job_data.get('department', {}) or {}
    exp = job_data.get('experienceLevel', {}) or {}
    emp_type = job_data.get('typeOfEmployment', {}) or {}
    industry = job_data.get('industry', {}) or {}
    func = job_data.get('function', {}) or {}

    # Build URLs
    job_id = job_data.get('id', '')
    job_url = f"https://jobs.smartrecruiters.com/{company_slug}/{job_id}"
    apply_url = job_data.get('applyUrl', '') or f"{job_url}-apply"

    return SmartRecruitersJob(
        id=job_id,
        title=job_data.get('name', ''),
        company_slug=company_slug,
        location=location_str,
        description=description,
        url=job_url,
        apply_url=apply_url,
        department=dept.get('label'),
        employment_type=emp_type.get('id'),
        location_type=location_type,
        experience_level=exp.get('id'),
        industry=industry.get('label'),
        function=func.get('label'),
        city=loc.get('city'),
        region=loc.get('region'),
        country_code=loc.get('country'),
        published_at=job_data.get('releasedDate')
    )


def fetch_smartrecruiters_jobs(
    company_slug: str,
    filter_titles: bool = False,
    filter_locations: bool = False,
    title_patterns: Optional[List[str]] = None,
    location_patterns: Optional[List[str]] = None,
    rate_limit: float = RATE_LIMIT_DELAY
) -> Tuple[List[SmartRecruitersJob], Dict]:
    """
    Fetch all jobs for a single SmartRecruiters company with pagination.

    Args:
        company_slug: The company's SmartRecruiters identifier
        filter_titles: Apply title filtering to remove non-target roles
        filter_locations: Apply location filtering to remove non-target cities
        title_patterns: Regex patterns for title filtering (loaded from config if None)
        location_patterns: Substring patterns for location filtering (loaded from config if None)
        rate_limit: Seconds to wait between paginated requests

    Returns:
        Tuple of (list of SmartRecruitersJob objects, stats dict)
    """
    stats = {
        'jobs_fetched': 0,
        'jobs_kept': 0,
        'filtered_by_title': 0,
        'filtered_by_location': 0,
        'error': None
    }

    headers = {
        'User-Agent': 'job-analytics-bot/1.0 (github.com/job-analytics)',
        'Accept': 'application/json'
    }

    # Load filter patterns if filtering enabled
    if filter_titles and title_patterns is None:
        from scrapers.greenhouse.greenhouse_scraper import load_title_patterns
        title_patterns = load_title_patterns(
            Path(__file__).parent.parent.parent / 'config' / 'smartrecruiters' / 'title_patterns.yaml'
        )

    if filter_locations and location_patterns is None:
        from scrapers.greenhouse.greenhouse_scraper import load_location_patterns
        location_patterns = load_location_patterns(
            Path(__file__).parent.parent.parent / 'config' / 'smartrecruiters' / 'location_patterns.yaml'
        )

    # Import filter functions
    if filter_titles or filter_locations:
        from scrapers.greenhouse.greenhouse_scraper import is_relevant_role, matches_target_location

    all_jobs_data = []

    try:
        # Paginate through results
        offset = 0
        while True:
            url = f"{SMARTRECRUITERS_API_URL}/{company_slug}/postings"
            params = {
                'offset': offset,
                'limit': PAGE_LIMIT
            }

            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 404:
                logger.warning(f"SmartRecruiters company not found: {company_slug}")
                stats['error'] = 'Company not found'
                return [], stats

            if response.status_code == 429:
                logger.warning(f"Rate limited for {company_slug}")
                stats['error'] = 'Rate limited'
                return [], stats

            response.raise_for_status()
            data = response.json()

            # API returns {totalFound, offset, limit, content: [...]}
            content = data.get('content', [])
            if not isinstance(content, list):
                logger.warning(f"Unexpected response format from {company_slug}")
                stats['error'] = 'Invalid response format'
                return [], stats

            all_jobs_data.extend(content)

            # Check if more pages
            total_found = data.get('totalFound', 0)
            if offset + PAGE_LIMIT >= total_found or not content:
                break

            offset += PAGE_LIMIT
            time.sleep(rate_limit)

        stats['jobs_fetched'] = len(all_jobs_data)

        # Parse and filter jobs
        jobs = []
        for job_data in all_jobs_data:
            title = job_data.get('name', '')

            # Build location string for filtering
            loc = job_data.get('location', {}) or {}
            location_parts = []
            if loc.get('city'):
                location_parts.append(loc['city'])
            if loc.get('region'):
                location_parts.append(loc['region'])
            if loc.get('country'):
                location_parts.append(loc['country'])
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

                # Also check remote flag
                if not location_matched:
                    is_remote = loc.get('remote', False)
                    if is_remote:
                        location_matched = True

                # Also check description for location keywords (catches multi-location roles)
                if not location_matched:
                    # Build description from jobAd sections for location check
                    job_ad = job_data.get('jobAd', {}) or {}
                    sections = job_ad.get('sections', {}) or {}
                    desc_text = ''
                    for section_key in ['jobDescription', 'qualifications', 'additionalInformation']:
                        section = sections.get(section_key, {}) or {}
                        desc_text += ' ' + section.get('text', '')
                    description_lower = desc_text.lower()
                    location_matched = any(
                        pattern.lower() in description_lower
                        for pattern in location_patterns
                    )

                if not location_matched:
                    stats['filtered_by_location'] += 1
                    continue

            # Fetch detail endpoint to get jobAd (description)
            # The list endpoint does NOT include description text
            ref_url = job_data.get('ref')
            if ref_url:
                try:
                    detail_response = requests.get(ref_url, headers=headers, timeout=30)
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        # Merge detail fields into job_data
                        job_data['jobAd'] = detail_data.get('jobAd')
                        job_data['applyUrl'] = detail_data.get('applyUrl')
                        job_data['compensation'] = detail_data.get('compensation')
                    else:
                        logger.warning(f"Detail fetch failed for {title[:40]}: HTTP {detail_response.status_code}")
                    time.sleep(rate_limit)
                except Exception as e:
                    logger.warning(f"Detail fetch error for {title[:40]}: {str(e)[:80]}")

            job = parse_smartrecruiters_job(job_data, company_slug)
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
        # Rate limit after final request
        time.sleep(rate_limit)

    return jobs, stats


def load_company_mapping(mapping_path: Optional[Path] = None) -> Dict:
    """
    Load company mapping from config file.

    Args:
        mapping_path: Path to smartrecruiters/company_mapping.json

    Returns:
        Dict with 'smartrecruiters' key containing company data
    """
    if mapping_path is None:
        mapping_path = Path(__file__).parent.parent.parent / 'config' / 'smartrecruiters' / 'company_mapping.json'

    if not mapping_path.exists():
        logger.warning(f"Company mapping not found: {mapping_path}")
        return {'smartrecruiters': {}}

    with open(mapping_path) as f:
        return json.load(f)


def fetch_all_smartrecruiters_companies(
    companies: Optional[List[str]] = None,
    filter_titles: bool = True,
    filter_locations: bool = True,
    rate_limit: float = RATE_LIMIT_DELAY,
    on_company_complete: Optional[callable] = None
) -> Tuple[List[SmartRecruitersJob], Dict]:
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
    sr_companies = mapping.get('smartrecruiters', {})

    if not sr_companies:
        logger.warning("No companies in SmartRecruiters mapping")
        return [], combined_stats

    # Filter to specified companies if provided
    if companies:
        companies_to_process = {
            name: data for name, data in sr_companies.items()
            if data.get('slug') in companies
        }
    else:
        companies_to_process = sr_companies

    # Load filter patterns once
    title_patterns = None
    location_patterns = None

    if filter_titles:
        try:
            from scrapers.greenhouse.greenhouse_scraper import load_title_patterns
            title_patterns = load_title_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'smartrecruiters' / 'title_patterns.yaml'
            )
        except Exception as e:
            logger.warning(f"Could not load title patterns: {e}")

    if filter_locations:
        try:
            from scrapers.greenhouse.greenhouse_scraper import load_location_patterns
            location_patterns = load_location_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'smartrecruiters' / 'location_patterns.yaml'
            )
        except Exception as e:
            logger.warning(f"Could not load location patterns: {e}")

    logger.info(f"Fetching from {len(companies_to_process)} SmartRecruiters companies...")

    for company_name, company_data in companies_to_process.items():
        slug = company_data.get('slug', '')
        if not slug:
            logger.warning(f"No slug for company: {company_name}")
            continue

        logger.info(f"  Fetching: {company_name} ({slug})")

        jobs, stats = fetch_smartrecruiters_jobs(
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
    Quick check if a company uses SmartRecruiters.

    Args:
        slug: Company identifier to check

    Returns:
        True if company exists on SmartRecruiters, False otherwise
    """
    try:
        response = requests.get(
            f"{SMARTRECRUITERS_API_URL}/{slug}/postings?limit=1",
            timeout=10
        )
        return response.status_code == 200
    except:
        return False


# Standalone test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Fetch jobs from SmartRecruiters API')
    parser.add_argument('--slug', type=str, help='Single company slug to test')
    parser.add_argument('--all', action='store_true', help='Fetch from all companies in mapping')
    parser.add_argument('--no-filter', action='store_true', help='Disable title/location filtering')
    parser.add_argument('--check', type=str, help='Check if company slug exists on SmartRecruiters')
    args = parser.parse_args()

    if args.check:
        exists = check_company_exists(args.check)
        print(f"Company '{args.check}' exists on SmartRecruiters: {exists}")

    elif args.slug:
        # Test single company
        jobs, stats = fetch_smartrecruiters_jobs(
            args.slug,
            filter_titles=not args.no_filter,
            filter_locations=not args.no_filter
        )
        print(f"\nFetched {len(jobs)} jobs from {args.slug}")
        for job in jobs[:5]:
            print(f"  - {job.title} ({job.location})")
            print(f"    Location type: {job.location_type}")
            print(f"    Experience: {job.experience_level}")
            print(f"    Department: {job.department}")
            print(f"    Description: {len(job.description)} chars")
        print(f"\nStats: {json.dumps(stats, indent=2)}")

    elif args.all:
        # Fetch from all companies
        jobs, stats = fetch_all_smartrecruiters_companies(
            filter_titles=not args.no_filter,
            filter_locations=not args.no_filter
        )
        print(f"\nTotal: {len(jobs)} jobs")
        print(f"Stats: {json.dumps(stats, indent=2)}")

    else:
        # Quick connectivity test
        print("Testing SmartRecruiters API connectivity...")
        print("Use --slug <identifier> to test a specific company")
        print("Use --check <identifier> to verify a company exists")
