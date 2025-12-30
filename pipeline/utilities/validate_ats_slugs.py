#!/usr/bin/env python3
"""
ATS Slug Validator

Validates company slugs against Greenhouse, Lever, or Ashby APIs.

Usage:
    # Validate all companies for a source
    python pipeline/utilities/validate_ats_slugs.py greenhouse
    python pipeline/utilities/validate_ats_slugs.py lever
    python pipeline/utilities/validate_ats_slugs.py ashby

    # Validate specific companies
    python pipeline/utilities/validate_ats_slugs.py greenhouse --companies stripe,airbnb
    python pipeline/utilities/validate_ats_slugs.py lever --companies figma,notion
"""

import json
import argparse
import time
import requests
from pathlib import Path
from typing import Dict, List, Tuple

# Config paths relative to repo root
CONFIG_PATHS = {
    'greenhouse': 'config/greenhouse/company_ats_mapping.json',
    'lever': 'config/lever/company_mapping.json',
    'ashby': 'config/ashby/company_mapping.json',
}

# Validation endpoints
VALIDATION_CONFIG = {
    'greenhouse': {
        'urls': [
            'https://job-boards.greenhouse.io/{slug}',
            'https://boards.greenhouse.io/{slug}',
            'https://job-boards.eu.greenhouse.io/{slug}',
            'https://boards.greenhouse.io/embed/job_board?for={slug}',
        ],
        'method': 'head',
    },
    'lever': {
        'urls': [
            'https://api.lever.co/v0/postings/{slug}',
            'https://api.eu.lever.co/v0/postings/{slug}',
        ],
        'method': 'get',
    },
    'ashby': {
        'urls': [
            'https://api.ashbyhq.com/posting-api/job-board/{slug}',
        ],
        'method': 'get',
    },
}


def load_companies(source: str) -> Dict[str, str]:
    """Load company name -> slug mapping from config."""
    repo_root = Path(__file__).parent.parent.parent
    config_path = repo_root / CONFIG_PATHS[source]

    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}")
        return {}

    with open(config_path) as f:
        data = json.load(f)

    companies = data.get(source, {})
    result = {}

    for name, info in companies.items():
        if isinstance(info, dict):
            result[name] = info.get('slug', '')
        else:
            result[name] = str(info)

    return result


def validate_slug(slug: str, source: str, timeout: int = 10) -> Tuple[bool, str]:
    """
    Validate a single slug against the ATS API.

    Returns: (is_valid, working_url or error_message)
    """
    config = VALIDATION_CONFIG[source]
    headers = {'User-Agent': 'job-analytics-validator/1.0'}

    for url_template in config['urls']:
        url = url_template.format(slug=slug)
        try:
            if config['method'] == 'get':
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)

            if response.status_code == 200:
                # For API endpoints, verify there's actual content
                if config['method'] == 'get':
                    try:
                        data = response.json()
                        # Lever/Ashby return arrays or objects
                        if isinstance(data, list) or isinstance(data, dict):
                            return True, url
                    except:
                        pass
                else:
                    return True, url

        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.RequestException:
            continue

    return False, "No valid endpoint found"


def validate_source(source: str, company_filter: List[str] = None) -> Dict:
    """
    Validate all companies for a source.

    Returns: {'valid': [...], 'invalid': [...]}
    """
    companies = load_companies(source)

    if not companies:
        return {'valid': [], 'invalid': []}

    # Filter if specific companies requested
    if company_filter:
        filter_lower = [c.lower() for c in company_filter]
        companies = {
            name: slug for name, slug in companies.items()
            if slug.lower() in filter_lower or name.lower() in filter_lower
        }

    print(f"\n{'='*60}")
    print(f"VALIDATING {source.upper()} ({len(companies)} companies)")
    print('='*60)

    results = {'valid': [], 'invalid': []}

    for i, (name, slug) in enumerate(sorted(companies.items()), 1):
        is_valid, detail = validate_slug(slug, source)

        if is_valid:
            status = "OK"
            results['valid'].append((name, slug))
        else:
            status = "XX"
            results['invalid'].append((name, slug, detail))

        print(f"[{i:3}/{len(companies)}] [{status}] {name:40} ({slug})")

        # Rate limit
        time.sleep(0.5)

    return results


def print_summary(results: Dict, source: str):
    """Print validation summary."""
    total = len(results['valid']) + len(results['invalid'])

    print(f"\n{'='*60}")
    print(f"SUMMARY: {source.upper()}")
    print('='*60)
    print(f"Total:   {total}")
    print(f"Valid:   {len(results['valid'])}")
    print(f"Invalid: {len(results['invalid'])}")

    if results['invalid']:
        print(f"\n{'='*60}")
        print("INVALID SLUGS (consider removing from config)")
        print('='*60)
        for name, slug, reason in results['invalid']:
            print(f"  {name:40} ({slug})")


def main():
    parser = argparse.ArgumentParser(
        description='Validate ATS company slugs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        'source',
        choices=['greenhouse', 'lever', 'ashby'],
        help='ATS platform to validate'
    )

    parser.add_argument(
        '--companies', '-c',
        type=str,
        help='Comma-separated list of company slugs or names to validate (default: all)'
    )

    args = parser.parse_args()

    company_filter = None
    if args.companies:
        company_filter = [c.strip() for c in args.companies.split(',')]

    results = validate_source(args.source, company_filter)
    print_summary(results, args.source)


if __name__ == '__main__':
    main()
