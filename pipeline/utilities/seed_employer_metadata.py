"""
Seed Employer Metadata
======================
Seeds the employer_metadata table from existing enriched_jobs data.

Creates entries with:
- canonical_name: lowercase employer name
- display_name: from ATS config files (source of truth) or most common casing variant
- employer_size: majority vote from existing jobs (optional)
- working_arrangement_default: NULL (populated manually or via hardcoded known companies)

Display Name Priority:
1. ATS config file key (e.g., "Nuro" from greenhouse/company_ats_mapping.json)
2. KNOWN_WORKING_ARRANGEMENTS display_name (manual overrides)
3. Most common capitalized variant from enriched_jobs data
4. Most common variant overall (fallback)

Usage:
    python -m pipeline.utilities.seed_employer_metadata --dry-run
    python -m pipeline.utilities.seed_employer_metadata --min-jobs 3
    python -m pipeline.utilities.seed_employer_metadata --seed-known

Options:
    --dry-run       Show what would be created without making changes
    --min-jobs N    Only create entries for employers with N+ jobs (default: 3)
    --seed-known    Also seed known company working arrangements (Harvey AI, etc.)
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


# Known company working arrangements (manually verified)
# These are companies where we know the policy from career pages/job postings
KNOWN_WORKING_ARRANGEMENTS = {
    'harvey ai': {'arrangement': 'hybrid', 'display_name': 'Harvey AI'},
    'intercom': {'arrangement': 'hybrid', 'display_name': 'Intercom'},
    # Add more as we verify them
    # 'gitlab': {'arrangement': 'remote', 'display_name': 'GitLab'},
    # 'zapier': {'arrangement': 'remote', 'display_name': 'Zapier'},
}

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


def seed_employer_metadata(dry_run: bool = False, min_jobs: int = 3, seed_known: bool = False):
    """
    Seed employer_metadata from existing enriched_jobs.
    """
    supabase = get_supabase()

    print("=" * 70)
    print("SEED EMPLOYER METADATA")
    print("=" * 70)
    print(f"Dry run: {dry_run}")
    print(f"Minimum jobs threshold: {min_jobs}")
    print(f"Seed known arrangements: {seed_known}")
    print()

    # Step 0: Load display names from config files (source of truth)
    print("[CONFIG] Loading display names from ATS config files...")
    config_display_names = load_display_names_from_config()
    print(f"[OK] Loaded {len(config_display_names)} display names from config")

    # Step 1: Fetch all employer names and sizes
    print("\n[DATA] Fetching employer data from enriched_jobs...")

    employer_data = defaultdict(lambda: {'names': [], 'sizes': []})
    offset = 0
    page_size = 1000

    while True:
        result = supabase.table("enriched_jobs") \
            .select("employer_name, employer_size") \
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

            size = row.get('employer_size')
            if size:
                employer_data[canonical]['sizes'].append(size)

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
        # Priority: 1) Config file, 2) DISPLAY_NAME_OVERRIDES, 3) KNOWN_WORKING_ARRANGEMENTS,
        #           4) Capitalized variant, 5) Most common
        name_counts = defaultdict(int)
        for name in data['names']:
            name_counts[name] += 1

        # Check config files first (source of truth for ATS companies)
        if canonical in config_display_names:
            display_name = config_display_names[canonical]
            display_name_source = 'config'
        # Check DISPLAY_NAME_OVERRIDES (manual overrides for Adzuna-only employers)
        elif canonical in DISPLAY_NAME_OVERRIDES:
            display_name = DISPLAY_NAME_OVERRIDES[canonical]
            display_name_source = 'override'
        # Check KNOWN_WORKING_ARRANGEMENTS (companies with known policies)
        elif canonical in KNOWN_WORKING_ARRANGEMENTS:
            display_name = KNOWN_WORKING_ARRANGEMENTS[canonical]['display_name']
            display_name_source = 'known'
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

        # Majority vote for employer_size (if available)
        employer_size = None
        if data['sizes']:
            size_counts = defaultdict(int)
            for s in data['sizes']:
                size_counts[s] += 1
            employer_size = max(size_counts.keys(), key=lambda s: size_counts[s])

        # Check if this is a known company with working arrangement
        known_info = KNOWN_WORKING_ARRANGEMENTS.get(canonical) if seed_known else None

        entries.append({
            'canonical_name': canonical,
            'display_name': display_name,
            'display_name_source': display_name_source,  # Track where display_name came from
            'employer_size': employer_size,
            'working_arrangement_default': known_info['arrangement'] if known_info else None,
            'working_arrangement_source': 'manual' if known_info else None,
            'job_count': job_count  # For sorting/display only
        })

    print(f"[OK] {len(entries)} employers meet threshold")
    print(f"[SKIP] {skipped} employers below threshold")

    # Display name source stats
    config_count = sum(1 for e in entries if e['display_name_source'] == 'config')
    override_count = sum(1 for e in entries if e['display_name_source'] == 'override')
    known_count_dn = sum(1 for e in entries if e['display_name_source'] == 'known')
    inferred_count = sum(1 for e in entries if e['display_name_source'] == 'inferred')
    print(f"\n[DISPLAY NAME SOURCES]")
    print(f"  From config files: {config_count}")
    print(f"  From DISPLAY_NAME_OVERRIDES: {override_count}")
    print(f"  From KNOWN_WORKING_ARRANGEMENTS: {known_count_dn}")
    print(f"  Inferred from data: {inferred_count}")

    if seed_known:
        known_count = sum(1 for e in entries if e['working_arrangement_default'])
        print(f"\n[KNOWN] {known_count} employers have known working arrangements")

    # Step 3: Show preview
    print(f"\n[PREVIEW] Top 20 by job count:")
    print("-" * 80)
    print(f"  {'Display Name':<30} {'Source':<10} {'Jobs':>5}  {'Size':<10}  WA")
    print("-" * 80)

    # Sort by job count for preview
    entries_sorted = sorted(entries, key=lambda e: e['job_count'], reverse=True)

    for entry in entries_sorted[:20]:
        job_count = entry['job_count']
        size = entry['employer_size'] or 'N/A'
        wa = entry['working_arrangement_default'] or '-'
        src = entry['display_name_source'][:8]
        print(f"  {entry['display_name'][:30]:<30} {src:<10} {job_count:>5}  {size:<10}  {wa}")

    if len(entries) > 20:
        print(f"  ... and {len(entries) - 20} more")

    # Step 4: Upsert to database
    if dry_run:
        print(f"\n[DRY RUN] Would create {len(entries)} employer_metadata entries")
        return

    print(f"\n[DB] Upserting {len(entries)} entries...")

    success = 0
    errors = 0

    for entry in entries:
        try:
            # Build data dict (exclude job_count, it's just for display)
            data = {
                'canonical_name': entry['canonical_name'],
                'display_name': entry['display_name'],
            }

            # Add optional fields only if not None
            if entry['employer_size']:
                data['employer_size'] = entry['employer_size']
            if entry['working_arrangement_default']:
                data['working_arrangement_default'] = entry['working_arrangement_default']
                data['working_arrangement_source'] = entry['working_arrangement_source']

            supabase.table("employer_metadata").upsert(
                data, on_conflict='canonical_name'
            ).execute()
            success += 1
        except Exception as e:
            print(f"   [ERROR] {entry['canonical_name']}: {e}")
            errors += 1

    print(f"\n[DONE] Success: {success}, Errors: {errors}")


def update_known_arrangements(dry_run: bool = False):
    """
    Update working_arrangement_default for known companies.
    Separate from seeding - can be run independently.
    """
    supabase = get_supabase()

    print("=" * 70)
    print("UPDATE KNOWN WORKING ARRANGEMENTS")
    print("=" * 70)
    print(f"Dry run: {dry_run}")
    print(f"Known companies: {len(KNOWN_WORKING_ARRANGEMENTS)}")
    print()

    for canonical, info in KNOWN_WORKING_ARRANGEMENTS.items():
        print(f"  {info['display_name']}: {info['arrangement']}")

        if not dry_run:
            try:
                supabase.table("employer_metadata").upsert({
                    'canonical_name': canonical,
                    'display_name': info['display_name'],
                    'working_arrangement_default': info['arrangement'],
                    'working_arrangement_source': 'manual'
                }, on_conflict='canonical_name').execute()
                print(f"    [OK] Updated")
            except Exception as e:
                print(f"    [ERROR] {e}")

    if dry_run:
        print(f"\n[DRY RUN] Would update {len(KNOWN_WORKING_ARRANGEMENTS)} entries")
    else:
        print(f"\n[DONE] Updated {len(KNOWN_WORKING_ARRANGEMENTS)} entries")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed employer_metadata table")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--min-jobs", type=int, default=3, help="Minimum jobs threshold")
    parser.add_argument("--seed-known", action="store_true", help="Include known working arrangements")
    parser.add_argument("--update-known-only", action="store_true", help="Only update known arrangements")
    args = parser.parse_args()

    if args.update_known_only:
        update_known_arrangements(dry_run=args.dry_run)
    else:
        seed_employer_metadata(dry_run=args.dry_run, min_jobs=args.min_jobs, seed_known=args.seed_known)
