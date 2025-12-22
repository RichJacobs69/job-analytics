"""
Lever Postings API Client

PURPOSE:
Fetch job postings from Lever's public Postings API (no auth required).
Similar to Adzuna client but with Greenhouse-quality full descriptions.

API Documentation: https://github.com/lever/postings-api

USAGE:
    from scrapers.lever.lever_fetcher import fetch_lever_jobs, fetch_all_lever_companies

    # Fetch from single company
    jobs = fetch_lever_jobs('spotify')

    # Fetch from all companies in mapping
    all_jobs = fetch_all_lever_companies()

    # With filtering
    jobs = fetch_lever_jobs('spotify', filter_titles=True, filter_locations=True)
"""

import sys
import json
import time
import logging
import requests
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from html import unescape

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lever API endpoints
LEVER_API_URLS = {
    "global": "https://api.lever.co/v0/postings",
    "eu": "https://api.eu.lever.co/v0/postings"
}

# Rate limiting: 1 request per second (conservative)
RATE_LIMIT_DELAY = 1.0


@dataclass
class LeverJob:
    """Parsed Lever job posting."""
    id: str
    title: str
    company_slug: str
    location: str
    description: str
    url: str
    apply_url: str
    team: Optional[str] = None
    department: Optional[str] = None
    commitment: Optional[str] = None  # Full-time, Part-time, etc.
    instance: str = "global"


def strip_html(html_content: str) -> str:
    """
    Strip HTML tags and decode entities from content.

    Args:
        html_content: Raw HTML string

    Returns:
        Plain text string
    """
    if not html_content:
        return ""

    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', ' ', html_content)
    # Decode HTML entities
    clean = unescape(clean)
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def build_full_description(job_data: Dict) -> str:
    """
    Build full job description from all available Lever fields.

    Concatenates:
    - descriptionPlain (main description)
    - lists (Responsibilities, Requirements, etc.)
    - additional (extra info)

    Args:
        job_data: Raw job dict from Lever API

    Returns:
        Combined plain text description
    """
    parts = []

    # Main description (plain text version)
    if job_data.get('descriptionPlain'):
        parts.append(job_data['descriptionPlain'])

    # Lists (Responsibilities, Requirements, etc.)
    for list_item in job_data.get('lists', []):
        list_text = list_item.get('text', '')
        list_content = strip_html(list_item.get('content', ''))
        if list_text and list_content:
            parts.append(f"\n{list_text}:\n{list_content}")

    # Additional info
    if job_data.get('additional'):
        additional = strip_html(job_data['additional'])
        if additional:
            parts.append(f"\nAdditional Information:\n{additional}")

    return '\n\n'.join(parts)


def parse_lever_job(job_data: Dict, company_slug: str, instance: str = "global") -> LeverJob:
    """
    Parse raw Lever API job data into LeverJob object.

    Args:
        job_data: Raw job dict from Lever API
        company_slug: The company's Lever site slug
        instance: 'global' or 'eu'

    Returns:
        LeverJob object
    """
    categories = job_data.get('categories', {})

    # Use allLocations if available (contains full list like ["Paris", "London"])
    # Fall back to single location field if allLocations not present
    all_locations = categories.get('allLocations', [])
    if all_locations and isinstance(all_locations, list):
        location = ' / '.join(all_locations)
    else:
        location = categories.get('location', '')

    return LeverJob(
        id=job_data.get('id', ''),
        title=job_data.get('text', ''),
        company_slug=company_slug,
        location=location,
        description=build_full_description(job_data),
        url=job_data.get('hostedUrl', ''),
        apply_url=job_data.get('applyUrl', ''),
        team=categories.get('team'),
        department=categories.get('department'),
        commitment=categories.get('commitment'),
        instance=instance
    )


def fetch_lever_jobs(
    site_slug: str,
    instance: str = "global",
    filter_titles: bool = False,
    filter_locations: bool = False,
    title_patterns: Optional[List[str]] = None,
    location_patterns: Optional[List[str]] = None,
    rate_limit: float = RATE_LIMIT_DELAY
) -> Tuple[List[LeverJob], Dict]:
    """
    Fetch all jobs for a single Lever site.

    Args:
        site_slug: The company's Lever site slug (e.g., 'spotify')
        instance: 'global' or 'eu'
        filter_titles: Apply title filtering to remove non-target roles
        filter_locations: Apply location filtering to remove non-target cities
        title_patterns: Regex patterns for title filtering (loaded from config if None)
        location_patterns: Substring patterns for location filtering (loaded from config if None)
        rate_limit: Seconds to wait after request

    Returns:
        Tuple of (list of LeverJob objects, stats dict)
    """
    stats = {
        'jobs_fetched': 0,
        'jobs_kept': 0,
        'filtered_by_title': 0,
        'filtered_by_location': 0,
        'error': None
    }

    base_url = LEVER_API_URLS.get(instance, LEVER_API_URLS['global'])
    url = f"{base_url}/{site_slug}?mode=json"

    headers = {
        'User-Agent': 'job-analytics-bot/1.0',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 404:
            logger.warning(f"Lever site not found: {site_slug} ({instance})")
            stats['error'] = 'Site not found'
            return [], stats

        response.raise_for_status()
        jobs_data = response.json()

        if not isinstance(jobs_data, list):
            logger.warning(f"Unexpected response format from {site_slug}")
            stats['error'] = 'Invalid response format'
            return [], stats

        stats['jobs_fetched'] = len(jobs_data)

        # Load filter patterns if filtering enabled
        if filter_titles and title_patterns is None:
            from scrapers.greenhouse.greenhouse_scraper import load_title_patterns
            title_patterns = load_title_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'lever' / 'title_patterns.yaml'
            )

        if filter_locations and location_patterns is None:
            from scrapers.greenhouse.greenhouse_scraper import load_location_patterns
            location_patterns = load_location_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'lever' / 'location_patterns.yaml'
            )

        # Import filter functions
        if filter_titles or filter_locations:
            from scrapers.greenhouse.greenhouse_scraper import is_relevant_role, matches_target_location

        # Parse and filter jobs
        jobs = []
        for job_data in jobs_data:
            title = job_data.get('text', '')
            # Use allLocations if available for filtering (contains full list like ["Paris", "London"])
            categories = job_data.get('categories', {})
            all_locations = categories.get('allLocations', [])
            if all_locations and isinstance(all_locations, list):
                location = ' / '.join(all_locations)
            else:
                location = categories.get('location', '')

            # Apply title filter
            if filter_titles and title_patterns:
                if not is_relevant_role(title, title_patterns):
                    stats['filtered_by_title'] += 1
                    continue

            # Apply location filter
            if filter_locations and location_patterns:
                # First check structured location field
                location_matched = matches_target_location(location, location_patterns)

                # If no match in structured field, check job description for location keywords
                # (catches multi-location roles like "SF / NYC / Denver")
                if not location_matched:
                    description_text = job_data.get('descriptionPlain', '') + ' ' + job_data.get('description', '')
                    description_lower = description_text.lower()
                    # Simple substring matching is safe now that problematic abbreviations are removed
                    location_matched = any(
                        pattern.lower() in description_lower
                        for pattern in location_patterns
                    )

                if not location_matched:
                    stats['filtered_by_location'] += 1
                    continue

            job = parse_lever_job(job_data, site_slug, instance)
            jobs.append(job)

        stats['jobs_kept'] = len(jobs)

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching from {site_slug}")
        stats['error'] = 'Timeout'
        return [], stats

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for {site_slug}: {e}")
        stats['error'] = str(e)[:100]
        return [], stats

    except json.JSONDecodeError:
        logger.error(f"Invalid JSON from {site_slug}")
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
        mapping_path: Path to lever/company_mapping.json

    Returns:
        Dict with 'lever' key containing company data
    """
    if mapping_path is None:
        mapping_path = Path(__file__).parent.parent.parent / 'config' / 'lever' / 'company_mapping.json'

    if not mapping_path.exists():
        logger.warning(f"Company mapping not found: {mapping_path}")
        return {'lever': {}}

    with open(mapping_path) as f:
        return json.load(f)


def fetch_all_lever_companies(
    companies: Optional[List[str]] = None,
    filter_titles: bool = True,
    filter_locations: bool = True,
    rate_limit: float = RATE_LIMIT_DELAY,
    on_company_complete: Optional[callable] = None
) -> Tuple[List[LeverJob], Dict]:
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
    lever_companies = mapping.get('lever', {})

    if not lever_companies:
        logger.warning("No companies in mapping")
        return [], combined_stats

    # Filter to specified companies if provided
    if companies:
        companies_to_process = {
            name: data for name, data in lever_companies.items()
            if data['slug'] in companies
        }
    else:
        companies_to_process = lever_companies

    # Load filter patterns once
    title_patterns = None
    location_patterns = None

    if filter_titles:
        try:
            from scrapers.greenhouse.greenhouse_scraper import load_title_patterns
            title_patterns = load_title_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'lever' / 'title_patterns.yaml'
            )
        except Exception as e:
            logger.warning(f"Could not load title patterns: {e}")

    if filter_locations:
        try:
            from scrapers.greenhouse.greenhouse_scraper import load_location_patterns
            location_patterns = load_location_patterns(
                Path(__file__).parent.parent.parent / 'config' / 'lever' / 'location_patterns.yaml'
            )
        except Exception as e:
            logger.warning(f"Could not load location patterns: {e}")

    logger.info(f"Fetching from {len(companies_to_process)} Lever companies...")

    for company_name, company_data in companies_to_process.items():
        slug = company_data['slug']
        instance = company_data.get('instance', 'global')

        logger.info(f"  Fetching: {company_name} ({slug})")

        jobs, stats = fetch_lever_jobs(
            site_slug=slug,
            instance=instance,
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

    parser = argparse.ArgumentParser(description='Fetch jobs from Lever API')
    parser.add_argument('--slug', type=str, help='Single company slug to test')
    parser.add_argument('--all', action='store_true', help='Fetch from all companies in mapping')
    parser.add_argument('--no-filter', action='store_true', help='Disable title/location filtering')
    args = parser.parse_args()

    if args.slug:
        # Test single company
        jobs, stats = fetch_lever_jobs(
            args.slug,
            filter_titles=not args.no_filter,
            filter_locations=not args.no_filter
        )
        print(f"\nFetched {len(jobs)} jobs from {args.slug}")
        for job in jobs[:5]:
            print(f"  - {job.title} ({job.location})")
            print(f"    Description: {len(job.description)} chars")
        print(f"\nStats: {json.dumps(stats, indent=2)}")

    elif args.all:
        # Fetch from all companies
        jobs, stats = fetch_all_lever_companies(
            filter_titles=not args.no_filter,
            filter_locations=not args.no_filter
        )
        print(f"\nTotal: {len(jobs)} jobs")
        print(f"Stats: {json.dumps(stats, indent=2)}")

    else:
        # Quick test with Spotify
        print("Testing with Spotify...")
        jobs, stats = fetch_lever_jobs('spotify', filter_titles=False, filter_locations=False)
        print(f"Fetched {len(jobs)} jobs")
        if jobs:
            job = jobs[0]
            print(f"\nSample job:")
            print(f"  Title: {job.title}")
            print(f"  Location: {job.location}")
            print(f"  URL: {job.url}")
            print(f"  Description length: {len(job.description)} chars")
            print(f"  Description preview: {job.description[:500]}...")
