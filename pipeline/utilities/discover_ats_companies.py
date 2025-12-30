#!/usr/bin/env python3
"""
ATS Company Discovery Tool

Discovers companies using Greenhouse, Lever, or Ashby via Google Custom Search API.
Validates discovered slugs and appends new companies to the relevant config file.

Setup:
    1. Create a Custom Search Engine at https://programmablesearchengine.google.com/
       - Set "Search the entire web" = ON
    2. Get API key from https://console.cloud.google.com/apis/credentials
    3. Add to .env:
       GOOGLE_CSE_API_KEY=your_api_key
       GOOGLE_CSE_ID=your_cse_id

Usage:
    # Discover for all platforms (Greenhouse, Lever, Ashby)
    python pipeline/utilities/discover_ats_companies.py all

    # Discover for a single platform
    python pipeline/utilities/discover_ats_companies.py ashby

    # Output to file instead of appending to config
    python pipeline/utilities/discover_ats_companies.py greenhouse --output results.json

    # Filter by job family
    python pipeline/utilities/discover_ats_companies.py lever --family data

    # Skip validation (faster but may include invalid slugs)
    python pipeline/utilities/discover_ats_companies.py ashby --no-validate
"""

import os
import re
import json
import argparse
import time
import requests
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()


# ============================================================================
# Configuration
# ============================================================================

# ATS URL patterns for slug extraction
ATS_CONFIG = {
    'greenhouse': {
        'slug_patterns': [
            r'job-boards\.greenhouse\.io/([a-zA-Z0-9_-]+)',
            r'boards\.greenhouse\.io/([a-zA-Z0-9_-]+)',
            r'board\.greenhouse\.io/([a-zA-Z0-9_-]+)',
            r'job-boards\.eu\.greenhouse\.io/([a-zA-Z0-9_-]+)',
            r'boards\.greenhouse\.io/embed/job_board\?for=([a-zA-Z0-9_-]+)',
            r'boards\.greenhouse\.io/embed/job_app\?for=([a-zA-Z0-9_-]+)',
        ],
        'search_query': 'site:job-boards.greenhouse.io OR site:boards.greenhouse.io',
        'config_path': Path('config/greenhouse/company_ats_mapping.json'),
        'config_key': 'greenhouse',
        'validate_urls': [
            'https://job-boards.greenhouse.io/{slug}',
            'https://boards.greenhouse.io/embed/job_board?for={slug}',
            'https://boards.greenhouse.io/{slug}',
        ],
    },
    'lever': {
        'slug_patterns': [
            r'jobs\.lever\.co/([a-zA-Z0-9_-]+)',
            r'jobs\.eu\.lever\.co/([a-zA-Z0-9_-]+)',
        ],
        'search_query': 'site:jobs.lever.co',
        'config_path': Path('config/lever/company_mapping.json'),
        'config_key': 'lever',
        'validate_urls': [
            'https://api.lever.co/v0/postings/{slug}',
        ],
    },
    'ashby': {
        'slug_patterns': [
            r'jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)',
        ],
        'search_query': 'site:jobs.ashbyhq.com',
        'config_path': Path('config/ashby/company_mapping.json'),
        'config_key': 'ashby',
        'validate_urls': [
            'https://api.ashbyhq.com/posting-api/job-board/{slug}',
        ],
    },
}

# Role queries by job family (from schema_taxonomy.yaml)
ROLE_QUERIES = {
    'product': ['"product manager"', '"growth PM"', '"technical PM"'],
    'data': ['"data engineer"', '"data scientist"', '"analytics engineer"', '"ML engineer"'],
    'delivery': ['"project manager"', '"scrum master"', '"delivery manager"'],
}

# Locations (from schema_taxonomy.yaml)
LOCATIONS = ['"San Francisco"', '"New York"', '"London"', '"Singapore"']

# Slugs to ignore (common non-company paths)
IGNORE_SLUGS = {'embed', 'job_board', 'jobs', 'careers', 'apply', 'posting', 'job_app'}

# Google Custom Search API
GOOGLE_CSE_API_KEY = os.getenv('GOOGLE_CSE_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')


# ============================================================================
# Google Custom Search API
# ============================================================================

def search_google(query: str, num_results: int = 10) -> List[str]:
    """
    Search Google using Custom Search API.

    Args:
        query: Search query
        num_results: Max results (API limit: 10 per request, 100/day free)

    Returns:
        List of URLs from search results
    """
    urls = []

    try:
        response = requests.get(
            'https://www.googleapis.com/customsearch/v1',
            params={
                'key': GOOGLE_CSE_API_KEY,
                'cx': GOOGLE_CSE_ID,
                'q': query,
                'num': min(num_results, 10),  # API max is 10
            },
            timeout=10
        )

        if response.status_code == 429:
            print("  [QUOTA] Daily limit reached (100/day)")
            return urls

        if response.status_code == 400:
            error = response.json().get('error', {}).get('message', 'Bad request')
            print(f"  [ERROR] {error}")
            return urls

        if response.status_code != 200:
            print(f"  [ERROR] HTTP {response.status_code}")
            return urls

        data = response.json()
        for item in data.get('items', []):
            url = item.get('link', '')
            if url:
                urls.append(url)

    except Exception as e:
        print(f"  [ERROR] {e}")

    return urls


# ============================================================================
# Slug Extraction & Validation
# ============================================================================

def extract_slugs(urls: List[str], platform: str) -> Set[str]:
    """Extract company slugs from URLs."""
    slugs = set()
    patterns = ATS_CONFIG[platform]['slug_patterns']

    for url in urls:
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                slug = match.group(1).lower()
                if slug not in IGNORE_SLUGS:
                    slugs.add(slug)
                break

    return slugs


def validate_slug(slug: str, platform: str, timeout: int = 10) -> bool:
    """Check if a slug is valid on the ATS platform."""
    headers = {'User-Agent': 'job-analytics-bot/1.0'}

    for url_template in ATS_CONFIG[platform]['validate_urls']:
        url = url_template.format(slug=slug)
        try:
            # For API endpoints, use GET
            if 'api.' in url:
                response = requests.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    return True
            else:
                response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
                if response.status_code == 200:
                    return True
        except:
            continue

    return False


# ============================================================================
# Config Management
# ============================================================================

def load_existing_slugs(platform: str) -> Set[str]:
    """Load existing slugs from config."""
    config_path = Path(__file__).parent.parent.parent / ATS_CONFIG[platform]['config_path']

    if not config_path.exists():
        return set()

    try:
        with open(config_path) as f:
            data = json.load(f)

        key = ATS_CONFIG[platform]['config_key']
        companies = data.get(key, {})

        slugs = set()
        for name, info in companies.items():
            if isinstance(info, dict):
                slugs.add(info.get('slug', '').lower())
            else:
                slugs.add(str(info).lower())

        return slugs
    except Exception as e:
        print(f"Warning: Could not load config: {e}")
        return set()


def save_to_config(platform: str, new_slugs: Set[str]) -> int:
    """Append new slugs to config file."""
    config_path = Path(__file__).parent.parent.parent / ATS_CONFIG[platform]['config_path']
    key = ATS_CONFIG[platform]['config_key']

    # Load existing
    if config_path.exists():
        with open(config_path) as f:
            data = json.load(f)
    else:
        data = {key: {}}

    if key not in data:
        data[key] = {}

    # Get existing slugs
    existing = {
        (info.get('slug') if isinstance(info, dict) else info).lower()
        for info in data[key].values()
    }

    added = 0
    for slug in sorted(new_slugs):
        if slug.lower() not in existing:
            name = slug.replace('-', ' ').replace('_', ' ').title()
            data[key][name] = {'slug': slug}
            added += 1

    if added > 0:
        # Update meta if present
        if '_meta' in data:
            data['_meta']['total_companies'] = len(data[key])
            data['_meta']['last_updated'] = datetime.now().strftime('%Y-%m-%d')

        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)

    return added


# ============================================================================
# Main Discovery Flow
# ============================================================================

def discover(
    platform: str,
    family: Optional[str] = None,
    validate: bool = True,
    output_file: Optional[str] = None
) -> Dict:
    """
    Main discovery flow:
    1. Generate search queries
    2. Scrape Google for each query
    3. Extract slugs from URLs
    4. Filter out existing slugs
    5. Validate new slugs
    6. Save to config or output file
    """
    print(f"\n{'='*60}")
    print(f"DISCOVERING {platform.upper()} COMPANIES")
    print('='*60)

    existing = load_existing_slugs(platform)
    print(f"Already tracking: {len(existing)} companies")

    # Build search queries
    base_query = ATS_CONFIG[platform]['search_query']
    if family:
        roles = ROLE_QUERIES.get(family, [])
    else:
        # All subfamilies when no family specified
        roles = ROLE_QUERIES['data'] + ROLE_QUERIES['product'] + ROLE_QUERIES['delivery']

    queries = [base_query]  # Basic query
    for role in roles:  # All roles
        queries.append(f'{base_query} {role}')
    for loc in LOCATIONS:  # All locations
        queries.append(f'{base_query} {loc}')

    # Check API keys upfront
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_ID:
        print("\n[ERROR] Missing Google Custom Search API credentials.")
        print("Add to .env:")
        print("  GOOGLE_CSE_API_KEY=your_api_key")
        print("  GOOGLE_CSE_ID=your_cse_id")
        print("\nSetup guide: https://programmablesearchengine.google.com/")
        return {'discovered': 0, 'validated': 0, 'added': 0}

    print(f"Running {len(queries)} search queries (10 results each)...\n")

    # Search via Google Custom Search API
    all_urls = []
    for i, query in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] {query[:60]}...")
        urls = search_google(query, num_results=10)
        all_urls.extend(urls)
        print(f"         Found {len(urls)} URLs")

        # Rate limit (be nice to the API)
        time.sleep(1)

    if not all_urls:
        print("\n[WARNING] No URLs found. Check your .env has:")
        print("  GOOGLE_CSE_API_KEY=your_api_key")
        print("  GOOGLE_CSE_ID=your_cse_id")
        return {'discovered': 0, 'validated': 0, 'added': 0}

    # Extract slugs
    all_slugs = extract_slugs(all_urls, platform)
    print(f"\nExtracted {len(all_slugs)} unique slugs")

    # Filter existing
    new_slugs = all_slugs - existing
    print(f"New (not in config): {len(new_slugs)}")

    if not new_slugs:
        print("No new companies found.")
        return {'discovered': len(all_slugs), 'validated': 0, 'added': 0}

    # Validate
    valid_slugs = set()
    if validate:
        print(f"\nValidating {len(new_slugs)} slugs...")
        for slug in sorted(new_slugs):
            is_valid = validate_slug(slug, platform)
            status = "[OK]" if is_valid else "[XX]"
            print(f"  {status} {slug}")
            if is_valid:
                valid_slugs.add(slug)
            time.sleep(0.5)
        print(f"\nValid: {len(valid_slugs)} / {len(new_slugs)}")
    else:
        valid_slugs = new_slugs
        print("(Skipping validation)")

    if not valid_slugs:
        return {'discovered': len(all_slugs), 'validated': 0, 'added': 0}

    # Save results
    if output_file:
        # Output to file
        output_path = Path(output_file)
        results = {
            'platform': platform,
            'discovered_at': datetime.now().isoformat(),
            'slugs': sorted(valid_slugs),
        }
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved {len(valid_slugs)} slugs to {output_file}")
        added = len(valid_slugs)
    else:
        # Append to config
        added = save_to_config(platform, valid_slugs)
        config_path = ATS_CONFIG[platform]['config_path']
        print(f"\nAdded {added} companies to {config_path}")

    return {'discovered': len(all_slugs), 'validated': len(valid_slugs), 'added': added}


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Discover ATS companies by scraping Google search results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        'platform',
        choices=['greenhouse', 'lever', 'ashby', 'all'],
        help='ATS platform to discover (or "all" for all platforms)'
    )

    parser.add_argument(
        '--family',
        choices=['product', 'data', 'delivery'],
        help='Filter by job family (default: data + product)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output to file instead of appending to config'
    )

    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip slug validation (faster but may include invalid)'
    )

    args = parser.parse_args()

    # Determine platforms to run
    if args.platform == 'all':
        platforms = ['greenhouse', 'lever', 'ashby']
    else:
        platforms = [args.platform]

    # Run discovery for each platform
    all_stats = {'discovered': 0, 'validated': 0, 'added': 0}
    for platform in platforms:
        stats = discover(
            platform=platform,
            family=args.family,
            validate=not args.no_validate,
            output_file=args.output
        )
        all_stats['discovered'] += stats['discovered']
        all_stats['validated'] += stats['validated']
        all_stats['added'] += stats['added']

    print(f"\n{'='*60}")
    print("SUMMARY" + (" (ALL PLATFORMS)" if len(platforms) > 1 else ""))
    print('='*60)
    print(f"Slugs discovered: {all_stats['discovered']}")
    print(f"Slugs validated:  {all_stats['validated']}")
    print(f"Companies added:  {all_stats['added']}")


if __name__ == '__main__':
    main()
