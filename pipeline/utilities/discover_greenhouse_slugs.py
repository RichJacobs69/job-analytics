#!/usr/bin/env python3
"""
Greenhouse Slug Discovery Tool

Discovers new Greenhouse companies from a curated seed list of tech companies
in London, NYC, and Denver. Validates they're scrapeable and optionally adds
to company_ats_mapping.json.

Usage:
    python pipeline/utilities/discover_greenhouse_slugs.py [--dry-run] [--batch-size 5] [--save]

Options:
    --dry-run       Test slugs but don't save results (default behavior)
    --save          Save valid slugs to company_ats_mapping.json
    --batch-size N  Number of concurrent tests (default: 5)
    --limit N       Limit total companies to test

Sources for seed list:
    - Y Combinator NYC/London companies (2023-2025)
    - Built In NYC/Colorado Best Places to Work (2024-2025)
    - London fintech Series B/C rounds (2024)
    - Denver/Boulder tech scene (2024)
    - Known Greenhouse customers from industry reports
"""

import asyncio
import json
import re
import argparse
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    exit(1)

# =============================================================================
# SEED LIST: Tech companies in London, NYC, Denver NOT already in mapping
# Compiled from web research on 2025-12-06
# =============================================================================

SEED_COMPANIES = {
    # =========================================================================
    # NYC - AI/ML & Data Companies
    # =========================================================================
    "Plaid": ["plaid"],
    "Brex": ["brex"],
    "Ramp": ["ramp"],
    "Current": ["current", "currentmobile"],
    "SmartAsset": ["smartasset"],
    "Enigma": ["enigma", "enigmaio"],
    "Dagster": ["dagster", "dagsterlabs"],
    "Pinecone": ["pinecone", "pineconeio"],
    "Runway": ["runwayml", "runway"],
    "Osmo": ["osmo", "osmoai"],
    "Modal": ["modal", "modallabs"],
    "Cohere": ["cohere", "cohereai"],
    "Weights & Biases": ["wandb", "weightsandbiases"],
    "Labelbox": ["labelbox"],
    "Weights and Biases": ["wandb"],

    # NYC - Fintech & Insurtech
    "Petal": ["petal", "petalcard"],
    "Hopscotch": ["hopscotch"],
    "Commonstock": ["commonstock"],
    "Percent": ["percent"],
    "NewFront Insurance": ["newfront", "newfrontinsurance"],
    "Capitolis": ["capitolis"],
    "Betterment": ["betterment"],
    "MoneyLion": ["moneylion"],

    # NYC - Healthtech
    "Tempus": ["tempus", "tempuslabs"],
    "Nourish": ["nourish", "nourishco"],
    "Galileo Health": ["galileohealth", "galileo"],
    "Thirty Madison": ["thirtymadison"],
    "Alto Pharmacy": ["altopharmacy", "alto"],
    "Cityblock Health": ["cityblock", "cityblockhealth"],
    "Dispatch Health": ["dispatchhealth"],
    "Capsule": ["capsule", "capsulepharmacy"],
    "Color Health": ["color", "colorhealth"],
    "Sword Health": ["swordhealth", "sword"],

    # NYC - Enterprise/B2B SaaS
    "Stainless": ["stainless", "stainlessapi"],
    "Ambient AI": ["ambientai", "ambient"],
    "Nautilus Labs": ["nautiluslabs", "nautilus"],
    "Fora Travel": ["fora", "foratravel"],
    "Gynger": ["gynger"],
    "EquityMultiple": ["equitymultiple"],
    "Grocery TV": ["grocerytv"],
    "Atom Finance": ["atomfinance", "atom"],
    "Able": ["able", "ableteam"],
    "Courier Health": ["courierhealth"],
    "Landis": ["landis", "landishomes"],
    "Check": ["check", "checkhq"],
    "Monograph": ["monograph"],
    "Metadata": ["metadata", "metadataio"],
    "Personio": ["personio"],
    "Census": ["census", "getcensus"],
    "Hex": ["hex", "hextechnologies"],
    "Hightouch": ["hightouch"],
    "dbt Labs": ["dbtlabs", "dbt"],
    "Prefect": ["prefect", "prefectio"],
    "Airbyte": ["airbyte"],
    "Temporal": ["temporal", "temporalio"],
    "LaunchDarkly": ["launchdarkly"],
    "Split": ["split", "splitio"],
    "Statsig": ["statsig"],
    "Eppo": ["eppo", "geteppo"],

    # NYC - Media & Consumer
    "Substack": ["substack"],
    "Cameo": ["cameo"],
    "Strava": ["strava"],
    "AllTrails": ["alltrails"],
    "ClassPass": ["classpass"],
    "Goldbelly": ["goldbelly"],
    "Cake": ["cake", "joincake"],

    # =========================================================================
    # LONDON - Fintech & Banking
    # =========================================================================
    "Revolut": ["revolut"],
    "Checkout.com": ["checkout", "checkoutcom"],
    "OakNorth": ["oaknorth"],
    "9fin": ["9fin"],
    "Abound": ["abound", "getabound"],
    "Yonder": ["yonder", "yondercard"],
    "Tembo Money": ["tembo", "tembomoney"],
    "Fundment": ["fundment"],
    "Thought Machine": ["thoughtmachine"],
    "Yapily": ["yapily"],
    "Tink": ["tink"],
    "Soldo": ["soldo"],
    "Tide": ["tide", "tidebanking"],
    "Marqeta": ["marqeta"],
    "Flywire": ["flywire"],
    "SaltPay": ["saltpay"],
    "Alma": ["alma", "getalma"],
    "Qonto": ["qonto"],

    # London - AI/Tech
    "Improbable": ["improbable"],
    "Darktrace": ["darktrace"],
    "Permutive": ["permutive"],
    "Let's Do This": ["letsdothis"],
    "Tractable": ["tractable"],
    "Bloomreach": ["bloomreach"],
    "Behavox": ["behavox"],
    "Faculty AI": ["faculty", "facultyai"],
    "Eigen Technologies": ["eigen", "eigentechnologies"],
    "Synthesia": ["synthesia"],
    "Wayve": ["wayve"],
    "Cera Care": ["cera", "ceracare"],
    "Featurespace": ["featurespace"],
    "Signal AI": ["signalai"],

    # London - Enterprise
    "Beamery": ["beamery"],
    "Paddle": ["paddle"],
    "Hopin": ["hopin"],
    "WorldRemit": ["worldremit"],
    "Cazoo": ["cazoo"],
    "Babylon Health": ["babylon", "babylonhealth"],
    "Bulb": ["bulb", "bulbenergy"],
    "Citymapper": ["citymapper"],
    "Depop": ["depop"],
    "Farfetch": ["farfetch"],
    "Unmind": ["unmind"],
    "Nested": ["nested"],
    "Currencycloud": ["currencycloud"],
    "Bought By Many": ["boughtbymany"],

    # =========================================================================
    # DENVER/BOULDER - Tech Companies
    # =========================================================================
    "Guild Education": ["guild", "guildeducation"],
    "Pax8": ["pax8"],
    "StackHawk": ["stackhawk"],
    "Ibotta": ["ibotta"],
    "Apto": ["apto"],
    "JumpCloud": ["jumpcloud"],
    "FlareHR": ["flarehr", "flare"],
    "Red Canary": ["redcanary"],
    "Cin7": ["cin7"],
    "Matillion": ["matillion"],
    "InDevR": ["indevr"],
    "Scythe Robotics": ["scythe", "scytherobotics"],
    "Sierra Space": ["sierraspace"],
    "Quantum Metric": ["quantummetric"],
    "SambaSafety": ["sambasafety"],
    "Zayo": ["zayo", "zayogroup"],
    "Welltok": ["welltok"],
    "SendGrid": ["sendgrid"],
    "LogRhythm": ["logrhythm"],
    "Faction": ["faction", "factioninc"],
    "OneTrust": ["onetrust"],
    "GoSpotCheck": ["gospotcheck"],
    "Dispatch": ["dispatch"],
    "Uplight": ["uplight"],
    "Gusto Denver": ["gustodenver"],
    "TeamSnap": ["teamsnap"],
    "TrackVia": ["trackvia"],
    "SpotHero": ["spothero"],

    # =========================================================================
    # Additional High-Value Companies (Various Locations)
    # =========================================================================
    "Notion": ["notion"],
    "Canva": ["canva"],
    "Figma": ["figma"],  # Already in mapping but testing pattern
    "Miro": ["miro"],
    "Airtable": ["airtable"],  # Already in mapping
    "Coda": ["coda", "codahq"],
    "ClickUp": ["clickup"],
    "Monday.com": ["monday", "mondaycom"],
    "Zapier": ["zapier"],
    "Typeform": ["typeform"],
    "Calendly": ["calendly"],
    "Loom": ["loom"],
    "Pitch": ["pitch"],
    "Mural": ["mural"],
    "Lucidchart": ["lucidchart"],
    "Amplitude": ["amplitude"],
    "Heap": ["heap", "heapanalytics"],
    "Mixpanel": ["mixpanel"],
    "Segment": ["segment"],
    "Customer.io": ["customerio"],
    "Braze": ["braze"],
    "Iterable": ["iterable"],
    "Klaviyo": ["klaviyo"],
    "Attentive": ["attentive"],
    "Gorgias": ["gorgias"],
    "Intercom": ["intercom"],  # Already in mapping
    "Zendesk": ["zendesk"],
    "Freshworks": ["freshworks"],
    "ServiceTitan": ["servicetitan"],
    "Toast": ["toast", "toasttab"],
    "Procore": ["procore"],
    "Jobber": ["jobber"],
    "Housecall Pro": ["housecallpro"],
    "Buildium": ["buildium"],
    "AppFolio": ["appfolio"],
    "Yardi": ["yardi"],
    "CoStar": ["costar"],
    "Zillow": ["zillow"],
    "Redfin": ["redfin"],
    "Compass": ["compass", "compassinc"],
    "Opendoor": ["opendoor"],  # Already in mapping
    "Offerpad": ["offerpad"],
    "Knock": ["knock", "knockaway"],
    "Homeward": ["homeward"],
    "Divvy Homes": ["divvyhomes", "divvy"],
    "Arrived": ["arrived", "arrivedhomes"],
}

# Base URLs to try (EXACTLY same as validate_greenhouse_slugs.py)
BASE_URLS = [
    "https://job-boards.greenhouse.io",
    "https://job-boards.eu.greenhouse.io",
    "https://boards.greenhouse.io",
    "https://board.greenhouse.io",
    "https://boards.greenhouse.io/embed/job_board?for=",
]


async def test_slug(slug: str, timeout: int = 15000) -> tuple[bool, str | None]:
    """
    Test if a Greenhouse slug is valid using Playwright.

    Uses EXACT same validation logic as validate_greenhouse_slugs.py:
    - Try all URL patterns (including embed pattern)
    - If ANY pattern loads without 404 error, it's VALID
    - If ALL patterns return 404, it's INVALID

    Returns: (is_valid, working_url or None)
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for base_url in BASE_URLS:
                # Handle embed URL pattern (ends with ?for=)
                if base_url.endswith('?for='):
                    url = f"{base_url}{slug}"
                else:
                    url = f"{base_url}/{slug}"

                page = None
                try:
                    page = await browser.new_page(
                        viewport={'width': 1280, 'height': 720}
                    )

                    try:
                        await page.goto(url, wait_until='networkidle', timeout=timeout)
                    except asyncio.TimeoutError:
                        # Timeout is not a 404 - still might be valid
                        if page:
                            await page.close()
                        continue

                    # Wait for page to fully load (EXACT match with validate script)
                    await page.wait_for_timeout(1000)

                    # Get page content
                    content = await page.content()
                    content_lower = content.lower()

                    # Check for various Greenhouse error messages (EXACT match)
                    error_messages = [
                        "sorry, but we can't find that page",
                        "the job board you were viewing is no longer active",
                        "page not found"
                    ]
                    is_error = any(msg in content_lower for msg in error_messages)

                    # Fallback: check for error page indicators
                    if not is_error:
                        # Genuine error pages are typically short; real job boards are large
                        if len(content) < 10000:  # Error pages usually < 10KB
                            is_error = True

                    if not is_error:
                        # Page loaded successfully without error message - it's valid!
                        await page.close()
                        await browser.close()
                        return True, url

                    await page.close()

                except Exception as e:
                    # Error on this URL, try next
                    if page:
                        try:
                            await page.close()
                        except:
                            pass
                    continue

            # All URLs either returned 404 or failed to load
            await browser.close()
            return False, None

    except Exception as e:
        return False, None


async def discover_company(company_name: str, slug_patterns: list[str]) -> tuple[str, str | None, str | None]:
    """
    Try to discover a valid Greenhouse slug for a company.

    Returns: (company_name, valid_slug or None, working_url or None)
    """
    for slug in slug_patterns:
        is_valid, url = await test_slug(slug)
        if is_valid:
            return company_name, slug, url

    return company_name, None, None


async def discover_batch(companies: dict, batch_size: int = 5) -> dict:
    """
    Discover valid slugs for a batch of companies.

    Returns dict with 'valid' and 'invalid' lists
    """
    results = {'valid': [], 'invalid': []}
    items = list(companies.items())
    total = len(items)

    for i in range(0, total, batch_size):
        batch = items[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"\n[Batch {batch_num}/{total_batches}]")

        tasks = [
            discover_company(company, slugs)
            for company, slugs in batch
        ]
        batch_results = await asyncio.gather(*tasks)

        for company, slug, url in batch_results:
            if slug:
                status = "OK"
                results['valid'].append((company, slug, url))
            else:
                status = "XX"
                results['invalid'].append(company)

            print(f"  [{status}] {company:40} -> {slug or 'not found'}")

        tested = min(i + batch_size, total)
        print(f"  Progress: {tested}/{total}")

    return results


def load_existing_mapping() -> set:
    """Load existing company names from mapping file."""
    mapping_path = Path(__file__).parent.parent.parent / 'config' / 'company_ats_mapping.json'

    try:
        with open(mapping_path) as f:
            mapping = json.load(f)

        existing = set()
        for company in mapping.get('greenhouse', {}).keys():
            existing.add(company.lower())

        return existing
    except FileNotFoundError:
        return set()


def save_results(results: dict, mapping_path: Path):
    """Save valid slugs to mapping file."""
    with open(mapping_path) as f:
        mapping = json.load(f)

    added = 0
    for company, slug, url in results['valid']:
        if company not in mapping['greenhouse']:
            mapping['greenhouse'][company] = {"slug": slug}
            added += 1
            print(f"  Added: {company} -> {slug}")

    if added > 0:
        with open(mapping_path, 'w') as f:
            json.dump(mapping, f, indent=4)
        print(f"\nSaved {added} new companies to {mapping_path}")
    else:
        print("\nNo new companies to add.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Test slugs but do not save (default)')
    parser.add_argument('--save', action='store_true',
                        help='Save valid slugs to company_ats_mapping.json')
    parser.add_argument('--batch-size', type=int, default=5,
                        help='Concurrent tests per batch (default: 5)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit total companies to test')

    args = parser.parse_args()

    print("=" * 80)
    print("GREENHOUSE SLUG DISCOVERY TOOL")
    print("=" * 80)
    print(f"\nSeed list contains {len(SEED_COMPANIES)} companies")

    # Filter out companies already in mapping
    existing = load_existing_mapping()
    to_test = {
        company: slugs
        for company, slugs in SEED_COMPANIES.items()
        if company.lower() not in existing
    }

    print(f"Already in mapping: {len(SEED_COMPANIES) - len(to_test)}")
    print(f"New companies to test: {len(to_test)}")

    if args.limit:
        to_test = dict(list(to_test.items())[:args.limit])
        print(f"Limited to: {len(to_test)}")

    if not to_test:
        print("\nNo new companies to test!")
        return

    print(f"\nTesting with batch size: {args.batch_size}")
    print("Status: [OK] = Valid Greenhouse board, [XX] = Not found")

    # Run discovery
    results = asyncio.run(discover_batch(to_test, args.batch_size))

    # Summary
    print("\n" + "=" * 80)
    print("DISCOVERY RESULTS")
    print("=" * 80)
    print(f"\nTested: {len(to_test)} companies")
    print(f"Valid (new Greenhouse boards): {len(results['valid'])}")
    print(f"Invalid (not found): {len(results['invalid'])}")

    if results['valid']:
        print(f"\n{'=' * 40}")
        print("VALID SLUGS FOUND")
        print("=" * 40)
        for company, slug, url in sorted(results['valid']):
            print(f"  {company:40} -> {slug}")

    # Save if requested
    if args.save and results['valid']:
        mapping_path = Path(__file__).parent.parent.parent / 'config' / 'company_ats_mapping.json'
        save_results(results, mapping_path)
    elif args.save:
        print("\nNo valid slugs to save.")
    else:
        print("\n[Dry run mode - use --save to add to mapping]")

    # Save discovery log
    log_path = Path(__file__).parent.parent.parent / 'output' / 'greenhouse_discovery_log.json'
    log_path.parent.mkdir(exist_ok=True)

    log = {
        'timestamp': datetime.now().isoformat(),
        'tested': len(to_test),
        'valid': [(c, s, u) for c, s, u in results['valid']],
        'invalid': results['invalid']
    }

    with open(log_path, 'w') as f:
        json.dump(log, f, indent=2)

    print(f"\nDiscovery log saved to: {log_path}")


if __name__ == '__main__':
    main()
