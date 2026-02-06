"""
Lever Company Discovery Module

PURPOSE:
Discover companies that use Lever ATS through multiple methods:
1. Scan existing raw_jobs table for jobs.lever.co URLs
2. Scrape tech directories (BuiltWith, TheirStack) for Lever customers
3. Manual additions from known tech companies

USAGE:
    python discover_lever_companies.py [--include-builtwith] [--output FILE]

OUTPUT:
    Generates a list of discovered Lever company slugs for validation.
"""

import re
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Set, Dict, List, Optional
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Regex pattern to extract Lever site slugs from URLs
LEVER_URL_PATTERN = re.compile(
    r'(?:https?://)?(?:jobs\.(?:eu\.)?lever\.co|api\.(?:eu\.)?lever\.co/v0/postings)/([a-zA-Z0-9_-]+)',
    re.IGNORECASE
)

# Known tech companies that use Lever (VERIFIED as of 2025-12-16)
# Note: Many companies have migrated away from Lever. Only verified active sites listed.
KNOWN_LEVER_COMPANIES = {
    # Verified active Lever sites (tested 2025-12-16)
    'lever': 'Lever',                  # 6 jobs (EU instance)
    'malt': 'Malt',                    # 23 jobs
    'plaid': 'Plaid',                  # 74 jobs
    'spotify': 'Spotify',              # 118 jobs
    'labelbox': 'Labelbox',            # 349 jobs
    'anchorage': 'Anchorage Digital',  # 62 jobs
    'attentive': 'Attentive',          # 45 jobs
    'outreach': 'Outreach',            # 31 jobs
    'neon': 'Neon',                    # 19 jobs
    'wealthfront': 'Wealthfront',      # 12 jobs
    '15five': '15Five',                # 1 job
    'anyscale': 'Anyscale',            # 1 job

    # Candidates from Desktop/lever check.txt (2025-12-16)
    # From Google search results - need validation
    'agicap': 'Agicap',
    'appen': 'Appen / CrowdGen',
    'applydigital': 'Apply Digital',
    'bee-talents': 'Bee Talents',
    'binance': 'Binance',
    'bloomon': 'Bloom & Wild Group',
    'breakwatertech': 'Breakwater Technology',
    'cloudinary': 'Cloudinary',
    'ethenalabs': 'Ethena Labs',
    'ethereumfoundation': 'Ethereum Foundation',
    'eve': 'Eve',
    'find': 'Find',
    'fnatic': 'Fnatic',
    'form': 'Form',
    'fresha': 'Fresha',
    'gettyimages': 'Getty Images',
    'gohighlevel': 'HighLevel',
    'imagexmedia': 'ImageX Media',
    'instructure': 'Instructure',
    'jiostar': 'JioStar',
    'medchart': 'Medchart',
    'metabase': 'Metabase',
    'mistral': 'Mistral AI',
    'moonpig': 'Moonpig',
    'nekohealth': 'Neko Health',
    'octoenergy': 'Octopus Energy Group',
    'offchainlabs': 'Offchain Labs',
    'openx': 'OpenX',
    'palantir': 'Palantir Technologies',
    'panopto': 'Panopto',
    'parcelvision': 'ParcelHero',
    'pibenchmark': 'PI Benchmark',
    'playonsports': 'PlayOn Sports',
    'proof': 'Proof',
    'quantco-': 'QuantCo',
    'rws': 'RWS / TrainAI',
    'safetyculture-2': 'SafetyCulture',
    'sapiosciences': 'Sapio Sciences',
    'scottlogic': 'Scott Logic',
    'sprinto': 'Sprinto',
    'sumo-digital': 'Sumo Group',
    'swissborg': 'SwissBorg',
    'teleport': 'Teleport',
    'terraformation': 'Terraformation',
    'thepieexecsearch': 'The PIE Executive Search',
    'trendyol': 'Trendyol',
    'welocalize': 'Welocalize',
    'wintermute-trading': 'Wintermute',
    'zopa': 'Zopa',
}


def discover_from_database() -> Set[str]:
    """
    Scan raw_jobs table for URLs containing jobs.lever.co or api.lever.co

    Returns:
        Set of unique Lever site slugs found in existing job data
    """
    try:
        from pipeline.db_connection import supabase

        logger.info("Scanning database for Lever URLs...")

        discovered_slugs = set()
        offset = 0
        page_size = 1000
        total_scanned = 0

        while True:
            # Query raw_jobs for posting_url containing lever.co
            result = supabase.table('raw_jobs') \
                .select('posting_url') \
                .or_('posting_url.ilike.%lever.co%,posting_url.ilike.%lever.co%') \
                .range(offset, offset + page_size - 1) \
                .execute()

            if not result.data:
                break

            for row in result.data:
                url = row.get('posting_url', '')
                match = LEVER_URL_PATTERN.search(url)
                if match:
                    slug = match.group(1).lower()
                    discovered_slugs.add(slug)

            total_scanned += len(result.data)
            offset += page_size

            if len(result.data) < page_size:
                break

        logger.info(f"Scanned {total_scanned} rows, found {len(discovered_slugs)} unique Lever slugs")
        return discovered_slugs

    except Exception as e:
        logger.warning(f"Database discovery failed: {e}")
        return set()


def discover_from_builtwith() -> Set[str]:
    """
    Attempt to discover Lever customers from BuiltWith.

    Note: This may require handling anti-scraping measures or using their API.
    Falls back gracefully if scraping fails.

    Returns:
        Set of discovered Lever site slugs
    """
    import requests

    logger.info("Attempting BuiltWith discovery...")

    discovered_slugs = set()

    try:
        # BuiltWith's public page - may have anti-scraping measures
        url = "https://trends.builtwith.com/websitelist/Lever"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            # Look for company domains in the response
            # BuiltWith typically lists company domains, not Lever slugs
            # We'd need to cross-reference or try common slug patterns

            # For now, log that we reached the page
            logger.info(f"BuiltWith page retrieved ({len(response.text)} bytes)")

            # Pattern to find potential company domains
            domain_pattern = re.compile(r'([a-zA-Z0-9-]+)\.com')
            domains = domain_pattern.findall(response.text)

            # Filter to reasonable company names (not generic domains)
            for domain in set(domains):
                if len(domain) > 3 and domain not in ['www', 'http', 'https', 'builtwith']:
                    # Try the domain as a potential Lever slug
                    discovered_slugs.add(domain.lower())

            logger.info(f"Found {len(discovered_slugs)} potential slugs from BuiltWith")
        else:
            logger.warning(f"BuiltWith returned status {response.status_code}")

    except Exception as e:
        logger.warning(f"BuiltWith discovery failed: {e}")

    return discovered_slugs


def discover_from_theirstack() -> Set[str]:
    """
    Attempt to discover Lever customers from TheirStack.

    Returns:
        Set of discovered Lever site slugs
    """
    import requests

    logger.info("Attempting TheirStack discovery...")

    discovered_slugs = set()

    try:
        url = "https://theirstack.com/en/technology/lever"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            logger.info(f"TheirStack page retrieved ({len(response.text)} bytes)")

            # Similar pattern matching for company names
            domain_pattern = re.compile(r'([a-zA-Z0-9-]+)\.com')
            domains = domain_pattern.findall(response.text)

            for domain in set(domains):
                if len(domain) > 3 and domain not in ['www', 'http', 'https', 'theirstack']:
                    discovered_slugs.add(domain.lower())

            logger.info(f"Found {len(discovered_slugs)} potential slugs from TheirStack")
        else:
            logger.warning(f"TheirStack returned status {response.status_code}")

    except Exception as e:
        logger.warning(f"TheirStack discovery failed: {e}")

    return discovered_slugs


def get_known_slugs() -> Set[str]:
    """
    Return the manually curated list of known Lever companies.

    Returns:
        Set of known Lever site slugs
    """
    return set(KNOWN_LEVER_COMPANIES.keys())


def discover_all(
    include_database: bool = True,
    include_builtwith: bool = False,
    include_theirstack: bool = False,
    include_known: bool = True
) -> Dict[str, Set[str]]:
    """
    Run all discovery methods and return combined results.

    Args:
        include_database: Scan existing raw_jobs for Lever URLs
        include_builtwith: Attempt BuiltWith scraping (may fail)
        include_theirstack: Attempt TheirStack scraping (may fail)
        include_known: Include manually curated known companies

    Returns:
        Dict mapping source name to set of discovered slugs
    """
    results = {}

    if include_known:
        results['known'] = get_known_slugs()
        logger.info(f"Known companies: {len(results['known'])} slugs")

    if include_database:
        results['database'] = discover_from_database()
        logger.info(f"Database discovery: {len(results['database'])} slugs")

    if include_builtwith:
        results['builtwith'] = discover_from_builtwith()
        logger.info(f"BuiltWith discovery: {len(results['builtwith'])} slugs")

    if include_theirstack:
        results['theirstack'] = discover_from_theirstack()
        logger.info(f"TheirStack discovery: {len(results['theirstack'])} slugs")

    # Combine all sources
    all_slugs = set()
    for source_slugs in results.values():
        all_slugs.update(source_slugs)

    results['combined'] = all_slugs

    logger.info(f"Total unique slugs discovered: {len(all_slugs)}")

    return results


def save_discovery_results(
    results: Dict[str, Set[str]],
    output_path: Optional[Path] = None
) -> Path:
    """
    Save discovery results to JSON file.

    Args:
        results: Discovery results from discover_all()
        output_path: Optional custom output path

    Returns:
        Path to saved file
    """
    if output_path is None:
        output_path = Path(__file__).parent.parent.parent / 'output' / 'lever_discovery_results.json'

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert sets to sorted lists for JSON serialization
    json_results = {
        'discovery_timestamp': datetime.utcnow().isoformat() + 'Z',
        'sources': {
            source: sorted(list(slugs))
            for source, slugs in results.items()
        },
        'summary': {
            'total_unique': len(results.get('combined', set())),
            'by_source': {
                source: len(slugs)
                for source, slugs in results.items()
                if source != 'combined'
            }
        }
    }

    with open(output_path, 'w') as f:
        json.dump(json_results, f, indent=2)

    logger.info(f"Discovery results saved to {output_path}")
    return output_path


def main():
    """CLI entry point for Lever company discovery."""
    parser = argparse.ArgumentParser(
        description='Discover companies that use Lever ATS',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic discovery (known + database)
  python discover_lever_companies.py

  # Include BuiltWith scraping (may fail)
  python discover_lever_companies.py --include-builtwith

  # Save to custom location
  python discover_lever_companies.py --output my_results.json
        """
    )

    parser.add_argument(
        '--include-builtwith',
        action='store_true',
        help='Attempt to scrape BuiltWith for Lever customers'
    )

    parser.add_argument(
        '--include-theirstack',
        action='store_true',
        help='Attempt to scrape TheirStack for Lever customers'
    )

    parser.add_argument(
        '--skip-database',
        action='store_true',
        help='Skip scanning the database for existing Lever URLs'
    )

    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output file path for discovery results'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("LEVER COMPANY DISCOVERY")
    logger.info("=" * 60)

    results = discover_all(
        include_database=not args.skip_database,
        include_builtwith=args.include_builtwith,
        include_theirstack=args.include_theirstack,
        include_known=True
    )

    output_path = save_discovery_results(results, args.output)

    # Print summary
    print("\n" + "=" * 60)
    print("DISCOVERY SUMMARY")
    print("=" * 60)
    print(f"Total unique slugs: {len(results['combined'])}")
    print("\nBy source:")
    for source, slugs in results.items():
        if source != 'combined':
            print(f"  {source}: {len(slugs)}")
    print(f"\nResults saved to: {output_path}")
    print("\nNext step: Run 'python pipeline/utilities/validate_ats_slugs.py lever' to confirm which slugs are active")


if __name__ == "__main__":
    main()
