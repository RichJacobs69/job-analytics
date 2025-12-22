"""
Lever Site Validation Module

PURPOSE:
Validate discovered Lever company slugs by calling the Lever Postings API.
For each slug, confirms:
1. Whether it's a valid Lever site
2. Which instance (global vs EU)
3. How many jobs are currently posted

USAGE:
    python validate_lever_sites.py [--input FILE] [--output FILE]

OUTPUT:
    Generates config/lever/company_mapping.json with validated companies.
"""

import sys
import json
import time
import logging
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

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
class ValidationResult:
    """Result of validating a single Lever slug."""
    slug: str
    is_valid: bool
    instance: Optional[str]  # 'global' or 'eu'
    job_count: int
    status_code: Optional[int]
    error: Optional[str]
    company_name: Optional[str]  # Extracted from first job if available
    sample_job_title: Optional[str]  # First job title for reference


def validate_slug(slug: str, rate_limit: float = RATE_LIMIT_DELAY) -> ValidationResult:
    """
    Validate a single Lever slug by calling the Postings API.

    Tries global instance first, then EU if global fails.

    Args:
        slug: The Lever site slug (e.g., 'figma', 'netflix')
        rate_limit: Seconds to wait after the request

    Returns:
        ValidationResult with status and job count
    """
    result = ValidationResult(
        slug=slug,
        is_valid=False,
        instance=None,
        job_count=0,
        status_code=None,
        error=None,
        company_name=None,
        sample_job_title=None
    )

    headers = {
        'User-Agent': 'job-analytics-bot/1.0 (https://github.com/yourrepo)',
        'Accept': 'application/json'
    }

    # Try global first, then EU
    for instance_name, base_url in LEVER_API_URLS.items():
        url = f"{base_url}/{slug}?mode=json"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            result.status_code = response.status_code

            if response.status_code == 200:
                jobs = response.json()

                if isinstance(jobs, list) and len(jobs) > 0:
                    result.is_valid = True
                    result.instance = instance_name
                    result.job_count = len(jobs)

                    # Extract company name from first job
                    first_job = jobs[0]
                    if 'categories' in first_job:
                        # Lever doesn't always include company name explicitly
                        # Use the team or department as a fallback
                        categories = first_job.get('categories', {})
                        result.company_name = categories.get('team') or slug.title()

                    result.sample_job_title = first_job.get('text', '')[:80]

                    logger.info(
                        f"  [VALID] {slug} ({instance_name}): {result.job_count} jobs"
                    )
                    break

                elif isinstance(jobs, list) and len(jobs) == 0:
                    # Valid slug but no jobs currently posted
                    # Continue to try EU in case this is the wrong instance
                    continue

            elif response.status_code == 404:
                # Not found on this instance, try next
                continue

            else:
                result.error = f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            result.error = "Request timeout"
        except requests.exceptions.RequestException as e:
            result.error = str(e)[:100]
        except json.JSONDecodeError:
            result.error = "Invalid JSON response"

    # Rate limit after request
    time.sleep(rate_limit)

    if not result.is_valid:
        logger.info(f"  [INVALID] {slug}: {result.error or 'No jobs found'}")

    return result


def validate_slugs(
    slugs: List[str],
    rate_limit: float = RATE_LIMIT_DELAY,
    progress_callback: Optional[callable] = None
) -> List[ValidationResult]:
    """
    Validate a list of Lever slugs.

    Args:
        slugs: List of slugs to validate
        rate_limit: Seconds between requests
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        List of ValidationResult objects
    """
    results = []
    total = len(slugs)

    logger.info(f"Validating {total} Lever slugs...")
    logger.info(f"Rate limit: {rate_limit}s between requests")
    logger.info(f"Estimated time: {total * rate_limit / 60:.1f} minutes")

    for i, slug in enumerate(slugs, 1):
        result = validate_slug(slug, rate_limit)
        results.append(result)

        if progress_callback:
            progress_callback(i, total)

        # Progress update every 10 slugs
        if i % 10 == 0:
            valid_so_far = sum(1 for r in results if r.is_valid)
            logger.info(f"Progress: {i}/{total} ({valid_so_far} valid so far)")

    return results


def load_discovery_results(input_path: Optional[Path] = None) -> List[str]:
    """
    Load discovered slugs from discovery results file.

    Args:
        input_path: Path to discovery results JSON

    Returns:
        List of unique slugs to validate
    """
    if input_path is None:
        input_path = Path(__file__).parent.parent.parent / 'output' / 'lever_discovery_results.json'

    if not input_path.exists():
        logger.warning(f"Discovery results not found at {input_path}")
        logger.info("Run discover_lever_companies.py first, or use --slugs to provide slugs directly")
        return []

    with open(input_path) as f:
        data = json.load(f)

    # Get combined slugs
    slugs = data.get('sources', {}).get('combined', [])
    logger.info(f"Loaded {len(slugs)} slugs from {input_path}")
    return slugs


def generate_company_mapping(
    results: List[ValidationResult],
    discovery_sources: Optional[List[str]] = None
) -> Dict:
    """
    Generate lever_company_mapping.json from validation results.

    Args:
        results: List of validation results
        discovery_sources: Optional list of discovery source names

    Returns:
        Dict in the format expected by lever_fetcher.py
    """
    valid_companies = {}

    for result in results:
        if result.is_valid:
            # Use slug as key (title-cased), not extracted team name
            # Team name from Lever API is often a department, not the company
            company_name = result.slug.replace('-', ' ').replace('_', ' ').title()

            valid_companies[company_name] = {
                'slug': result.slug,
                'instance': result.instance,
                'job_count': result.job_count
            }

    mapping = {
        'lever': valid_companies,
        '_meta': {
            'validated_at': datetime.utcnow().isoformat() + 'Z',
            'discovery_sources': discovery_sources or ['unknown'],
            'total_companies': len(valid_companies),
            'total_jobs_available': sum(r.job_count for r in results if r.is_valid)
        }
    }

    return mapping


def save_company_mapping(mapping: Dict, output_path: Optional[Path] = None) -> Path:
    """
    Save company mapping to config file.

    Args:
        mapping: Company mapping dict
        output_path: Optional custom output path

    Returns:
        Path to saved file
    """
    if output_path is None:
        output_path = Path(__file__).parent.parent.parent / 'config' / 'lever' / 'company_mapping.json'

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(mapping, f, indent=2)

    logger.info(f"Company mapping saved to {output_path}")
    return output_path


def save_validation_report(
    results: List[ValidationResult],
    output_path: Optional[Path] = None
) -> Path:
    """
    Save detailed validation report.

    Args:
        results: List of validation results
        output_path: Optional custom output path

    Returns:
        Path to saved file
    """
    if output_path is None:
        output_path = Path(__file__).parent.parent.parent / 'output' / 'lever_validation_report.json'

    output_path.parent.mkdir(parents=True, exist_ok=True)

    valid_results = [r for r in results if r.is_valid]
    invalid_results = [r for r in results if not r.is_valid]

    report = {
        'validation_timestamp': datetime.utcnow().isoformat() + 'Z',
        'summary': {
            'total_tested': len(results),
            'valid': len(valid_results),
            'invalid': len(invalid_results),
            'success_rate': f"{len(valid_results) / len(results) * 100:.1f}%" if results else "0%",
            'total_jobs_found': sum(r.job_count for r in valid_results)
        },
        'valid_sites': [asdict(r) for r in valid_results],
        'invalid_sites': [asdict(r) for r in invalid_results],
        'by_instance': {
            'global': len([r for r in valid_results if r.instance == 'global']),
            'eu': len([r for r in valid_results if r.instance == 'eu'])
        }
    }

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"Validation report saved to {output_path}")
    return output_path


def main():
    """CLI entry point for Lever site validation."""
    parser = argparse.ArgumentParser(
        description='Validate discovered Lever company slugs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate from discovery results
  python validate_lever_sites.py

  # Validate specific slugs
  python validate_lever_sites.py --slugs figma,netflix,notion

  # Custom input/output
  python validate_lever_sites.py --input my_slugs.json --output my_mapping.json
        """
    )

    parser.add_argument(
        '--input', '-i',
        type=Path,
        help='Input file with discovery results (default: output/lever_discovery_results.json)'
    )

    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output file for company mapping (default: config/lever/company_mapping.json)'
    )

    parser.add_argument(
        '--slugs',
        type=str,
        help='Comma-separated list of slugs to validate (overrides --input)'
    )

    parser.add_argument(
        '--rate-limit',
        type=float,
        default=RATE_LIMIT_DELAY,
        help=f'Seconds between API requests (default: {RATE_LIMIT_DELAY})'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("LEVER SITE VALIDATION")
    logger.info("=" * 60)

    # Get slugs to validate
    if args.slugs:
        slugs = [s.strip().lower() for s in args.slugs.split(',')]
        logger.info(f"Validating {len(slugs)} slugs from command line")
        discovery_sources = ['cli']
    else:
        slugs = load_discovery_results(args.input)
        if not slugs:
            return
        discovery_sources = ['discovery_results']

    # Validate
    results = validate_slugs(slugs, rate_limit=args.rate_limit)

    # Generate outputs
    mapping = generate_company_mapping(results, discovery_sources)
    mapping_path = save_company_mapping(mapping, args.output)
    report_path = save_validation_report(results)

    # Print summary
    valid_count = sum(1 for r in results if r.is_valid)
    total_jobs = sum(r.job_count for r in results if r.is_valid)

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total slugs tested: {len(results)}")
    print(f"Valid sites: {valid_count}")
    print(f"Invalid sites: {len(results) - valid_count}")
    print(f"Total jobs available: {total_jobs:,}")
    print(f"\nCompany mapping saved to: {mapping_path}")
    print(f"Validation report saved to: {report_path}")

    if valid_count > 0:
        print("\nTop companies by job count:")
        sorted_results = sorted(
            [r for r in results if r.is_valid],
            key=lambda x: x.job_count,
            reverse=True
        )
        for r in sorted_results[:10]:
            print(f"  {r.slug}: {r.job_count} jobs ({r.instance})")

    print("\nNext step: Run lever_fetcher.py to fetch jobs from validated companies")


if __name__ == "__main__":
    main()
