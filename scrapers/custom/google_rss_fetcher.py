"""
Google Careers XML Feed Parser

PURPOSE:
Fetch job postings from Google's official careers XML feed.
No authentication required, no rate limiting concerns.

XML Feed: https://www.google.com/about/careers/applications/jobs/feed.xml

NOTE: Despite the .xml extension, this is NOT an RSS feed. It's a custom XML format:
    <jobs>
      <job>
        <jobid>123456</jobid>
        <title>Software Engineer</title>
        <description>...</description>
        <url>https://careers.google.com/jobs/results/...</url>
        <locations>
          <location><city>London</city><country>UK</country></location>
        </locations>
      </job>
    </jobs>

USAGE:
    from scrapers.enterprise.google_rss_fetcher import fetch_google_rss_jobs

    # Fetch with default filtering
    jobs, stats = fetch_google_rss_jobs()

    # Fetch without filtering
    jobs, stats = fetch_google_rss_jobs(filter_titles=False, filter_locations=False)
"""

import sys
import logging
import requests
import re
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlparse, parse_qs

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Google Careers RSS feed URL
GOOGLE_RSS_URL = "https://www.google.com/about/careers/applications/jobs/feed.xml"

# Request timeout (feed is large, ~10MB)
REQUEST_TIMEOUT = 120


@dataclass
class GoogleJob:
    """Parsed Google job posting from RSS feed."""
    id: str
    title: str
    company: str  # Always "Google" for this source
    location: str
    description: str
    url: str
    apply_url: str
    department: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None


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


def extract_job_id(url: str) -> str:
    """
    Extract job ID from Google careers URL.

    URLs look like:
    https://www.google.com/about/careers/applications/jobs/results/123456789

    Args:
        url: Google careers job URL

    Returns:
        Job ID string or hash of URL if ID not found
    """
    if not url:
        # Generate unique ID for jobs without URLs (shouldn't happen in practice)
        import uuid
        return f"google_unknown_{uuid.uuid4().hex[:8]}"

    # Try to extract numeric ID from URL path
    match = re.search(r'/results/(\d+)', url)
    if match:
        return f"google_{match.group(1)}"

    # Try query parameter
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if 'id' in params:
        return f"google_{params['id'][0]}"

    # Fallback to hash
    return f"google_{hashlib.md5(url.encode()).hexdigest()[:12]}"


def extract_location(job_elem: ET.Element) -> str:
    """
    Extract location from Google XML job element.

    Google XML structure:
        <locations>
          <location>
            <city>Mountain View</city>
            <state>CA</state>
            <country>USA</country>
          </location>
          <location>
            <city>San Bruno</city>
            <state>CA</state>
            <country>USA</country>
          </location>
        </locations>

    Args:
        job_elem: XML Element for the job

    Returns:
        Location string (first location) or "Unknown"
    """
    locations_elem = job_elem.find('locations')
    if locations_elem is None:
        return "Unknown"

    # Get all location elements
    location_elems = locations_elem.findall('location')
    if not location_elems:
        return "Unknown"

    # Build location strings for all locations
    location_strs = []
    for loc in location_elems:
        city = loc.find('city')
        state = loc.find('state')
        country = loc.find('country')

        parts = []
        if city is not None and city.text:
            parts.append(city.text.strip())
        if state is not None and state.text:
            parts.append(state.text.strip())
        if country is not None and country.text:
            parts.append(country.text.strip())

        if parts:
            location_strs.append(", ".join(parts))

    # Return first location (primary), but log if multiple
    if location_strs:
        if len(location_strs) > 1:
            logger.debug(f"Job has {len(location_strs)} locations, using first: {location_strs[0]}")
        return location_strs[0]

    return "Unknown"


def extract_salary_from_description(description: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Extract salary information from job description text.

    Google embeds salary in the description like:
    "The US base salary range for this full-time position is $141,000-$202,000 + bonus + equity + benefits."

    Args:
        description: Job description text (HTML or plain)

    Returns:
        Tuple of (salary_min, salary_max, currency) or (None, None, None)
    """
    if not description:
        return None, None, None

    # Look for salary pattern in description
    # Pattern: "$XXX,XXX-$XXX,XXX" or "$XXX,XXX - $XXX,XXX"
    salary_pattern = r'\$(\d{1,3}(?:,\d{3})*)\s*[-–]\s*\$(\d{1,3}(?:,\d{3})*)'
    match = re.search(salary_pattern, description)

    if match:
        try:
            salary_min = int(match.group(1).replace(',', ''))
            salary_max = int(match.group(2).replace(',', ''))
            return salary_min, salary_max, 'USD'
        except ValueError:
            pass

    return None, None, None


def load_title_patterns() -> List[str]:
    """Load title filter patterns from Greenhouse config (reuse existing)."""
    config_path = Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'title_patterns.yaml'
    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            patterns = config.get('relevant_title_patterns', [])
            logger.debug(f"Loaded {len(patterns)} title patterns from {config_path}")
            return patterns
    except Exception as e:
        logger.warning(f"Could not load title patterns: {e}")
        return []


def load_location_patterns() -> List[str]:
    """Load location filter patterns from Greenhouse config (reuse existing)."""
    config_path = Path(__file__).parent.parent.parent / 'config' / 'greenhouse' / 'location_patterns.yaml'
    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            patterns = config.get('target_locations', [])
            logger.debug(f"Loaded {len(patterns)} location patterns from {config_path}")
            return patterns
    except Exception as e:
        logger.warning(f"Could not load location patterns: {e}")
        return []


def is_relevant_role(title: str, patterns: List[str]) -> bool:
    """
    Check if job title matches relevant role patterns.

    Args:
        title: Job title string
        patterns: List of regex patterns

    Returns:
        True if title matches any pattern
    """
    if not title or not patterns:
        return True  # No filtering if no patterns

    title_lower = title.lower()
    for pattern in patterns:
        try:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return True
        except re.error:
            # Treat as substring match if invalid regex
            if pattern.lower() in title_lower:
                return True
    return False


def matches_target_location(location: str, patterns: List[str]) -> bool:
    """
    Check if location matches target location patterns.

    Args:
        location: Job location string
        patterns: List of location substrings to match

    Returns:
        True if location matches any pattern
    """
    if not location or not patterns:
        return True  # No filtering if no patterns

    location_lower = location.lower()
    for pattern in patterns:
        if pattern.lower() in location_lower:
            return True
    return False


def fetch_google_rss_jobs(
    filter_titles: bool = True,
    filter_locations: bool = True,
) -> Tuple[List[GoogleJob], Dict]:
    """
    Fetch and parse Google careers RSS feed.

    Args:
        filter_titles: Apply title-based filtering (default: True)
        filter_locations: Apply location-based filtering (default: True)

    Returns:
        Tuple of (list of GoogleJob objects, stats dict)
    """
    stats = {
        'total_in_feed': 0,
        'filtered_by_title': 0,
        'filtered_by_location': 0,
        'jobs_kept': 0,
        'errors': 0,
    }

    # Load filter patterns
    title_patterns = load_title_patterns() if filter_titles else []
    location_patterns = load_location_patterns() if filter_locations else []

    logger.info(f"Fetching Google careers XML feed from {GOOGLE_RSS_URL}")
    logger.info(f"Title filtering: {filter_titles} ({len(title_patterns)} patterns)")
    logger.info(f"Location filtering: {filter_locations} ({len(location_patterns)} patterns)")

    try:
        response = requests.get(GOOGLE_RSS_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch XML feed: {e}")
        stats['errors'] = 1
        return [], stats

    # Parse XML
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        logger.error(f"Failed to parse XML: {e}")
        stats['errors'] = 1
        return [], stats

    jobs = []

    # Google uses custom XML format with <jobs><job>...</job></jobs>
    job_elems = root.findall('.//job')
    stats['total_in_feed'] = len(job_elems)
    logger.info(f"Found {len(job_elems)} total jobs in XML feed")

    for job_elem in job_elems:
        try:
            # Extract basic fields
            title_elem = job_elem.find('title')
            url_elem = job_elem.find('url')
            desc_elem = job_elem.find('description')
            jobid_elem = job_elem.find('jobid')
            employer_elem = job_elem.find('employer')  # Team/division (e.g., "YouTube")

            if title_elem is None or url_elem is None:
                continue

            title = title_elem.text.strip() if title_elem.text else ""
            url = url_elem.text.strip() if url_elem.text else ""
            description_raw = desc_elem.text if desc_elem is not None and desc_elem.text else ""
            description = strip_html(description_raw)

            # Get job ID directly from XML or extract from URL
            if jobid_elem is not None and jobid_elem.text:
                job_id = f"google_{jobid_elem.text.strip()}"
            else:
                job_id = extract_job_id(url)

            # Get department/team from employer field
            department = employer_elem.text.strip() if employer_elem is not None and employer_elem.text else None

            # Extract location from nested <locations> structure
            location = extract_location(job_elem)

            # Apply filters
            if filter_titles and title_patterns:
                if not is_relevant_role(title, title_patterns):
                    stats['filtered_by_title'] += 1
                    continue

            if filter_locations and location_patterns:
                if not matches_target_location(location, location_patterns):
                    stats['filtered_by_location'] += 1
                    continue

            # Extract salary from description text
            salary_min, salary_max, salary_currency = extract_salary_from_description(description_raw)

            # Create job object
            job = GoogleJob(
                id=job_id,
                title=title,
                company="Google",
                location=location,
                description=description,
                url=url,
                apply_url=url,  # Google uses same URL for viewing and applying
                department=department,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
            )
            jobs.append(job)
            stats['jobs_kept'] += 1

        except Exception as e:
            logger.warning(f"Error parsing job element: {e}")
            stats['errors'] += 1
            continue

    logger.info(f"Google XML fetch complete: {stats['jobs_kept']} jobs kept "
                f"(filtered: {stats['filtered_by_title']} by title, "
                f"{stats['filtered_by_location']} by location)")

    return jobs, stats


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch Google careers from XML feed")
    parser.add_argument("--no-filter-titles", action="store_true",
                        help="Disable title filtering")
    parser.add_argument("--no-filter-locations", action="store_true",
                        help="Disable location filtering")
    parser.add_argument("--limit", type=int, default=10,
                        help="Limit number of jobs to display (default: 10)")
    args = parser.parse_args()

    jobs, stats = fetch_google_rss_jobs(
        filter_titles=not args.no_filter_titles,
        filter_locations=not args.no_filter_locations,
    )

    print(f"\n=== Google XML Feed Stats ===")
    print(f"Total in feed: {stats['total_in_feed']}")
    print(f"Filtered by title: {stats['filtered_by_title']}")
    print(f"Filtered by location: {stats['filtered_by_location']}")
    print(f"Jobs kept: {stats['jobs_kept']}")
    print(f"Errors: {stats['errors']}")

    print(f"\n=== Sample Jobs (first {args.limit}) ===")
    for job in jobs[:args.limit]:
        print(f"\n{job.title}")
        print(f"  Location: {job.location}")
        if job.department:
            print(f"  Team: {job.department}")
        print(f"  URL: {job.url}")
        if job.salary_min:
            print(f"  Salary: ${job.salary_min:,} - ${job.salary_max:,} {job.salary_currency or ''}")
        print(f"  Description: {job.description[:200]}...")
