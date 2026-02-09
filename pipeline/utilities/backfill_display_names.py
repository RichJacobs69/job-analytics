"""
Backfill Display Names
======================
One-time backfill to fix employer_metadata rows where display_name was set
to the lowercase canonical_name instead of properly-cased names from ATS configs.

Loads display names from all 5 ATS config files (Greenhouse, Lever, Ashby,
Workable, SmartRecruiters) plus DISPLAY_NAME_OVERRIDES, then updates rows
where display_name == canonical_name (the lowercase default).

Usage:
    python -m pipeline.utilities.backfill_display_names              # Dry run (default)
    python -m pipeline.utilities.backfill_display_names --apply      # Apply changes
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv()

# Import shared overrides from seed script
from pipeline.utilities.seed_employer_metadata import DISPLAY_NAME_OVERRIDES


def load_display_name_map() -> dict:
    """
    Load display names from all ATS configs with dual-key lookup.

    For Greenhouse, keys by slug (slug == canonical_name in DB).
    For other sources, keys by both slug and display_name.lower()
    since the DB canonical_name may be either.

    Returns:
        dict: canonical_name (lowercase) -> display_name (proper casing)
    """
    display_names = {}
    config_dir = PROJECT_ROOT / 'config'

    # Start with manual overrides (highest priority)
    display_names.update(DISPLAY_NAME_OVERRIDES)

    # Greenhouse: slug is the canonical_name
    gh_path = config_dir / 'greenhouse' / 'company_ats_mapping.json'
    if gh_path.exists():
        with open(gh_path) as f:
            data = json.load(f)
            gh_companies = data.get('greenhouse', data)
            for name, info in gh_companies.items():
                if isinstance(info, dict) and 'slug' in info:
                    canonical = info['slug'].lower().strip()
                    if canonical not in display_names:
                        display_names[canonical] = name

    # Non-Greenhouse sources: dual-key by slug and display_name.lower()
    sources = [
        ('lever', 'lever'),
        ('ashby', 'ashby'),
        ('workable', 'workable'),
        ('smartrecruiters', 'smartrecruiters'),
    ]

    for source_dir, source_key in sources:
        path = config_dir / source_dir / 'company_mapping.json'
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
            companies = data.get(source_key, data)
            for name, info in companies.items():
                if isinstance(info, dict) and 'slug' in info:
                    # Key by slug
                    canonical = info['slug'].lower().strip()
                    if canonical not in display_names:
                        display_names[canonical] = name
                    # Key by display_name.lower()
                    canonical_from_name = name.lower().strip()
                    if canonical_from_name not in display_names:
                        display_names[canonical_from_name] = name

    return display_names


# Words that should stay uppercase when title-casing company names
ACRONYMS = {
    # General
    'ai', 'ml', 'it', 'hr', 'uk', 'us', 'eu', 'hq',
    'io', 'vr', 'ar', 'xr', 'qa', 'ux', 'ui', 'cx', 'dx',
    'nyc', 'usa', 'llc', 'inc', 'plc', 'api', 'cto',
    'svp', 'vp', 'dba', 'saas', 'b2b', 'b2c', 'd2c',
    # Company acronyms commonly appearing in multi-word names
    'hp', 'td', 'ab', 'ad', 'abb', 'abc', 'abm', 'abs',
    'acs', 'aeg', 'aws', 'bdo', 'bny', 'cgi', 'cnn', 'dbs',
    'dxc', 'gsk', 'hpe', 'ibm', 'ihg', 'itv', 'jll', 'kbr',
    'kkr', 'ntt', 'rbc', 'rsm', 'rtx', 'sap', 'ubs', 'wpp',
    'wsp', 'wtw', 'amd', 'dpr', 'erm', 'hdr', 'pvh',
}

# Short brand names that should stay title-cased, not uppercased.
# Everything else that is 2-3 alpha chars gets uppercased (HP, GSK, AMD, etc.)
SHORT_BRAND_NAMES = {
    'arm', 'arc', 'box', 'cos', 'eon', 'eos', 'fal', 'fay', 'fin',
    'fox', 'gap', 'hud', 'ing', 'ion', 'ki', 'mux', 'on', 'rec',
    'res', 'rho', 'ro', 'sim', 'sky', 'spa', 'sur', 'wex', 'wix',
    'wiz', 'zip', 'alt', 'edo', 'dat', 'vec', 'sj',
}

# Ordinal suffixes that title() incorrectly capitalizes (e.g. "1St" -> "1st")
import re
_ORDINAL_RE = re.compile(r'(\d+)(St|Nd|Rd|Th)\b', re.IGNORECASE)


def smart_title_case(name: str) -> str:
    """
    Title-case a company name with acronym awareness.

    Applies str.title(), uppercases known acronyms, fixes ordinals.
    For single-word names that are 2-3 alpha chars (e.g. "hp", "gsk"),
    uppercases them unless they are known brand names (Box, Sky, etc.).
    """
    titled = name.title()
    words = titled.split()

    # Single-word short name: likely an acronym (HP, GSK, AMD)
    if len(words) == 1:
        lower = words[0].lower()
        if lower in ACRONYMS:
            return words[0].upper()
        if len(lower) <= 3 and lower.isalpha() and lower not in SHORT_BRAND_NAMES:
            return words[0].upper()
        return words[0]

    result = []
    for word in words:
        lower = word.lower()
        if lower in ACRONYMS:
            result.append(word.upper())
        else:
            # Fix ordinals: "1St" -> "1st", "22Nd" -> "22nd"
            word = _ORDINAL_RE.sub(lambda m: m.group(1) + m.group(2).lower(), word)
            result.append(word)
    return ' '.join(result)


def get_supabase():
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")
    return create_client(url, key)


def backfill_display_names(apply: bool = False):
    """
    Backfill display_name for employer_metadata rows where
    display_name == canonical_name (lowercase default).
    """
    supabase = get_supabase()

    print("=" * 70)
    print("BACKFILL EMPLOYER DISPLAY NAMES")
    print("=" * 70)
    print(f"Mode: {'APPLY' if apply else 'DRY RUN'}")
    print()

    # Step 1: Load display name map
    print("[CONFIG] Loading display names from ATS configs + overrides...")
    name_map = load_display_name_map()
    print(f"[OK] Loaded {len(name_map)} display name mappings")

    # Step 2: Fetch all employer_metadata rows (paginated)
    print("\n[DATA] Fetching employer_metadata rows...")
    all_rows = []
    offset = 0
    page_size = 1000

    while True:
        result = supabase.table("employer_metadata") \
            .select("canonical_name, display_name") \
            .range(offset, offset + page_size - 1) \
            .execute()

        if not result.data:
            break

        all_rows.extend(result.data)

        if len(result.data) < page_size:
            break
        offset += page_size

    print(f"[OK] Fetched {len(all_rows)} employer_metadata rows")

    # Step 3: Find rows that need fixing
    fixable_config = []   # From ATS config / overrides
    fixable_titlecase = []  # From smart title-case fallback
    already_correct = 0

    for row in all_rows:
        canonical = row['canonical_name']
        current_display = row.get('display_name', '')

        if current_display != canonical:
            # display_name already differs from canonical -- already set
            already_correct += 1
            continue

        if canonical in name_map:
            new_display = name_map[canonical]
            fixable_config.append({
                'canonical_name': canonical,
                'current': current_display,
                'new': new_display,
                'source': 'config',
            })
        else:
            # Fallback: smart title-case
            new_display = smart_title_case(canonical)
            if new_display != canonical:
                fixable_titlecase.append({
                    'canonical_name': canonical,
                    'current': current_display,
                    'new': new_display,
                    'source': 'titlecase',
                })

    fixable = fixable_config + fixable_titlecase

    # Step 4: Print statistics
    print(f"\n[STATS]")
    print(f"  Total rows checked:    {len(all_rows)}")
    print(f"  Already correct:       {already_correct}")
    print(f"  Fixable from config:   {len(fixable_config)}")
    print(f"  Fixable from titlecase: {len(fixable_titlecase)}")
    print(f"  Total to update:       {len(fixable)}")

    if not fixable:
        print("\n[DONE] Nothing to fix.")
        return

    # Step 5: Preview
    print(f"\n[PREVIEW] First 30 fixes:")
    print("-" * 75)
    print(f"  {'Current (lowercase)':<30} {'New (proper casing)':<30} {'Source':<10}")
    print("-" * 75)

    for item in sorted(fixable, key=lambda x: x['canonical_name'])[:30]:
        print(f"  {item['current'][:30]:<30} {item['new'][:30]:<30} {item['source']:<10}")

    if len(fixable) > 30:
        print(f"  ... and {len(fixable) - 30} more")

    # Step 6: Apply
    if not apply:
        print(f"\n[DRY RUN] Would update {len(fixable)} rows.")
        print("Run with --apply to make changes.")
        return

    print(f"\n[APPLY] Updating {len(fixable)} rows...")
    success = 0
    errors = 0

    for item in fixable:
        try:
            supabase.table("employer_metadata").update({
                'display_name': item['new'],
            }).eq('canonical_name', item['canonical_name']).execute()
            success += 1
        except Exception as e:
            print(f"  [ERROR] {item['canonical_name']}: {e}")
            errors += 1

    print(f"\n[DONE] Updated: {success}, Errors: {errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backfill employer display names from ATS configs"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply changes (default is dry run)"
    )
    args = parser.parse_args()

    backfill_display_names(apply=args.apply)
