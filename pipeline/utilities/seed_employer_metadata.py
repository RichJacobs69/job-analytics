"""
Seed Employer Metadata
======================
Seeds the employer_metadata table from existing enriched_jobs data.

Creates entries with:
- canonical_name: lowercase employer name
- display_name: from ATS config files (source of truth) or most common casing variant

NOTE: employer_size and working_arrangement_default are NOT set by this script.
These fields are manually curated directly in the database. The seed script
preserves any existing manual entries (working_arrangement_source='manual').

Display Name Priority:
1. DISPLAY_NAME_OVERRIDES (manual overrides - highest priority)
2. ATS config file key (e.g., "Nuro" from greenhouse/company_ats_mapping.json)
3. Most common capitalized variant from enriched_jobs data
4. Most common variant overall (fallback)

Usage:
    python -m pipeline.utilities.seed_employer_metadata --dry-run
    python -m pipeline.utilities.seed_employer_metadata --min-jobs 3

Options:
    --dry-run       Show what would be created without making changes
    --min-jobs N    Only create entries for employers with N+ jobs (default: 3)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv()


# Display name overrides for companies not in ATS configs (e.g., Adzuna-only employers)
# These ensure proper casing even when source data is lowercase
DISPLAY_NAME_OVERRIDES = {
    # Big Tech
    'amazon': 'Amazon',
    'google': 'Google',
    'meta': 'Meta',
    'oracle': 'Oracle',
    'microsoft': 'Microsoft',
    'microsoft corporation': 'Microsoft Corporation',
    'apple': 'Apple',
    'ibm': 'IBM',

    # Finance
    'capital one': 'Capital One',
    'jpmorgan chase': 'JPMorgan Chase',
    'jpmorgan chase bank, n.a.': 'JPMorgan Chase Bank, N.A.',
    'jpmorgan chase & co.': 'JPMorgan Chase & Co.',
    'jpmorganchase': 'JPMorganChase',
    'goldman sachs': 'Goldman Sachs',
    'blackrock': 'BlackRock',
    'bny mellon': 'BNY Mellon',
    'american express': 'American Express',
    'mastercard': 'Mastercard',
    'visa': 'Visa',
    'hsbc': 'HSBC',
    'mufg': 'MUFG',
    'citi': 'Citi',
    'barclays': 'Barclays',
    'sofi': 'SoFi',
    's&p global': 'S&P Global',
    'u.s. bank': 'U.S. Bank',
    'london stock exchange group': 'London Stock Exchange Group',

    # Consulting/Professional Services
    'deloitte': 'Deloitte',
    'pwc': 'PwC',
    'ey': 'EY',
    'kpmg': 'KPMG',
    'accenture': 'Accenture',
    'capgemini': 'Capgemini',
    'guidehouse': 'Guidehouse',
    'cognizant': 'Cognizant',
    'turner & townsend': 'Turner & Townsend',
    'tata consultancy services': 'Tata Consultancy Services',

    # Defense/Aerospace
    'northrop grumman': 'Northrop Grumman',
    'lockheed martin': 'Lockheed Martin',
    'raytheon': 'Raytheon',
    'boeing': 'Boeing',

    # Media/Entertainment
    'nbc universal': 'NBC Universal',
    'nbcuniversal': 'NBCUniversal',
    'the walt disney company': 'The Walt Disney Company',
    'bloomberg': 'Bloomberg',
    'twitch': 'Twitch',

    # Tech
    'uber': 'Uber',
    'salesforce': 'Salesforce',
    'cisco': 'Cisco',
    'unity technologies': 'Unity Technologies',
    'tubi': 'Tubi',
    'strava': 'Strava',
    'digitalocean': 'DigitalOcean',
    'rippling': 'Rippling',
    'scale ai': 'Scale AI',
    'ibotta': 'Ibotta',
    'crusoe': 'Crusoe',
    'lumen': 'Lumen',
    'trimble': 'Trimble',
    'echostar': 'EchoStar',

    # Healthcare/Insurance
    'humana': 'Humana',
    'genentech': 'Genentech',
    'pfizer': 'Pfizer',
    'cvs health': 'CVS Health',
    'usaa': 'USAA',
    'cardinal health': 'Cardinal Health',
    'highmark health': 'Highmark Health',
    'maximus': 'Maximus',

    # Other
    'cbre': 'CBRE',
    'sephora': 'Sephora',
    'pernod ricard': 'Pernod Ricard',
    'western union': 'Western Union',
    'nanyang technological university': 'Nanyang Technological University',
    'flyzipline': 'Zipline',
    'launch potato': 'Launch Potato',
    'policy expert': 'Policy Expert',
}


def load_display_names_from_config() -> dict:
    """
    Load canonical display names from ATS config files.

    Config files use the proper company name as the key (e.g., "Nuro", "Harvey AI")
    and store the slug separately. This makes the config key the source of truth
    for display_name.

    Returns:
        dict: Mapping of canonical_name (lowercase) -> display_name (proper casing)
    """
    display_names = {}
    config_dir = PROJECT_ROOT / 'config'

    # Greenhouse: config/greenhouse/company_ats_mapping.json
    # Structure: {"greenhouse": {"Nuro": {"slug": "nuro"}, ...}}
    gh_path = config_dir / 'greenhouse' / 'company_ats_mapping.json'
    if gh_path.exists():
        with open(gh_path) as f:
            data = json.load(f)
            gh_companies = data.get('greenhouse', data)  # Handle both structures
            for display_name, info in gh_companies.items():
                if isinstance(info, dict) and 'slug' in info:
                    canonical = info['slug'].lower().strip()
                    display_names[canonical] = display_name

    # Lever: config/lever/company_mapping.json
    # Structure: {"lever": {"15Five": {"slug": "15five"}, ...}}
    lever_path = config_dir / 'lever' / 'company_mapping.json'
    if lever_path.exists():
        with open(lever_path) as f:
            data = json.load(f)
            lever_companies = data.get('lever', data)
            for display_name, info in lever_companies.items():
                if isinstance(info, dict) and 'slug' in info:
                    canonical = info['slug'].lower().strip()
                    # Don't overwrite if already set (Greenhouse takes precedence)
                    if canonical not in display_names:
                        display_names[canonical] = display_name

    # Ashby: config/ashby/company_mapping.json
    # Structure: {"ashby": {"Harvey AI": {"slug": "harvey"}, ...}}
    ashby_path = config_dir / 'ashby' / 'company_mapping.json'
    if ashby_path.exists():
        with open(ashby_path) as f:
            data = json.load(f)
            ashby_companies = data.get('ashby', data)
            for display_name, info in ashby_companies.items():
                if isinstance(info, dict) and 'slug' in info:
                    canonical = info['slug'].lower().strip()
                    # Don't overwrite if already set
                    if canonical not in display_names:
                        display_names[canonical] = display_name

    return display_names


def get_supabase():
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")
    return create_client(url, key)


def seed_employer_metadata(dry_run: bool = False, min_jobs: int = 3):
    """
    Seed employer_metadata from existing enriched_jobs.

    Only sets canonical_name and display_name. Preserves any existing
    employer_size or working_arrangement fields (manually curated in DB).
    """
    supabase = get_supabase()

    print("=" * 70)
    print("SEED EMPLOYER METADATA")
    print("=" * 70)
    print(f"Dry run: {dry_run}")
    print(f"Minimum jobs threshold: {min_jobs}")
    print()

    # Step 0: Load display names from config files (source of truth)
    print("[CONFIG] Loading display names from ATS config files...")
    config_display_names = load_display_names_from_config()
    print(f"[OK] Loaded {len(config_display_names)} display names from config")

    # Step 1: Fetch all employer names
    print("\n[DATA] Fetching employer data from enriched_jobs...")

    employer_data = defaultdict(lambda: {'names': []})
    offset = 0
    page_size = 1000

    while True:
        result = supabase.table("enriched_jobs") \
            .select("employer_name") \
            .range(offset, offset + page_size - 1) \
            .execute()

        if not result.data:
            break

        for row in result.data:
            name = row.get('employer_name')
            if not name:
                continue

            canonical = name.lower().strip()
            employer_data[canonical]['names'].append(name)

        if len(result.data) < page_size:
            break
        offset += page_size

    print(f"[OK] Found {len(employer_data)} unique employers (by canonical name)")

    # Step 2: Compute metadata for each employer
    print(f"\n[COMPUTE] Processing employers with >= {min_jobs} jobs...")

    entries = []
    skipped = 0

    for canonical, data in employer_data.items():
        job_count = len(data['names'])

        if job_count < min_jobs:
            skipped += 1
            continue

        # Find best display_name variant
        # Priority: 1) DISPLAY_NAME_OVERRIDES, 2) Config file, 3) Capitalized variant, 4) Most common
        name_counts = defaultdict(int)
        for name in data['names']:
            name_counts[name] += 1

        # Check DISPLAY_NAME_OVERRIDES first (manual overrides take precedence)
        if canonical in DISPLAY_NAME_OVERRIDES:
            display_name = DISPLAY_NAME_OVERRIDES[canonical]
            display_name_source = 'override'
        # Check config files (ATS company mappings)
        elif canonical in config_display_names:
            display_name = config_display_names[canonical]
            display_name_source = 'config'
        else:
            # Fall back to data-inferred: prefer capitalized variants
            capitalized_variants = {n: c for n, c in name_counts.items() if n and n[0].isupper()}

            if capitalized_variants:
                # Pick most common capitalized variant
                display_name = max(capitalized_variants.keys(), key=lambda n: capitalized_variants[n])
            else:
                # Fall back to most common overall
                display_name = max(name_counts.keys(), key=lambda n: name_counts[n])
            display_name_source = 'inferred'

        entries.append({
            'canonical_name': canonical,
            'display_name': display_name,
            'display_name_source': display_name_source,  # Track where display_name came from
            'job_count': job_count  # For sorting/display only
        })

    print(f"[OK] {len(entries)} employers meet threshold")
    print(f"[SKIP] {skipped} employers below threshold")

    # Display name source stats
    config_count = sum(1 for e in entries if e['display_name_source'] == 'config')
    override_count = sum(1 for e in entries if e['display_name_source'] == 'override')
    inferred_count = sum(1 for e in entries if e['display_name_source'] == 'inferred')
    print(f"\n[DISPLAY NAME SOURCES]")
    print(f"  From config files: {config_count}")
    print(f"  From DISPLAY_NAME_OVERRIDES: {override_count}")
    print(f"  Inferred from data: {inferred_count}")

    # Step 3: Show preview
    print(f"\n[PREVIEW] Top 20 by job count:")
    print("-" * 55)
    print(f"  {'Display Name':<30} {'Source':<10} {'Jobs':>5}")
    print("-" * 55)

    # Sort by job count for preview
    entries_sorted = sorted(entries, key=lambda e: e['job_count'], reverse=True)

    for entry in entries_sorted[:20]:
        job_count = entry['job_count']
        src = entry['display_name_source'][:8]
        print(f"  {entry['display_name'][:30]:<30} {src:<10} {job_count:>5}")

    if len(entries) > 20:
        print(f"  ... and {len(entries) - 20} more")

    # Step 4: Upsert to database
    if dry_run:
        print(f"\n[DRY RUN] Would create {len(entries)} employer_metadata entries")
        return

    print(f"\n[DB] Upserting {len(entries)} entries...")
    print("[NOTE] Only updating canonical_name and display_name.")
    print("[NOTE] employer_size and working_arrangement fields are preserved if already set.")

    success = 0
    errors = 0

    for entry in entries:
        try:
            # Only upsert canonical_name and display_name
            # This preserves any existing employer_size or working_arrangement fields
            # which are manually curated directly in the database
            supabase.table("employer_metadata").upsert({
                'canonical_name': entry['canonical_name'],
                'display_name': entry['display_name'],
            }, on_conflict='canonical_name').execute()
            success += 1
        except Exception as e:
            print(f"   [ERROR] {entry['canonical_name']}: {e}")
            errors += 1

    print(f"\n[DONE] Success: {success}, Errors: {errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed employer_metadata table")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--min-jobs", type=int, default=3, help="Minimum jobs threshold")
    args = parser.parse_args()

    seed_employer_metadata(dry_run=args.dry_run, min_jobs=args.min_jobs)
