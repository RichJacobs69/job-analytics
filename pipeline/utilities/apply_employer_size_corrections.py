"""
Apply employer size corrections to employer_metadata table.

This script applies high-confidence corrections identified from manual review:
1. Updates misclassified employer_size values
2. Deletes recruitment agencies that shouldn't be in employer_metadata

Usage:
    python pipeline/utilities/apply_employer_size_corrections.py --dry-run
    python pipeline/utilities/apply_employer_size_corrections.py --apply
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.db_connection import supabase


# High-confidence size corrections: canonical_name -> new_size
SIZE_CORRECTIONS = {
    # Startups that should be Enterprise (500+ employees)
    "openai": "enterprise",
    "lucidmotors": "enterprise",
    "zoox": "enterprise",
    "coreweave": "enterprise",
    "flyzipline": "enterprise",
    "ramp": "enterprise",
    "headway": "enterprise",
    "nuro": "enterprise",
    "oscar": "enterprise",  # Oscar Health 3000+ employees

    # Startups that should be Scaleup (51-500 employees)
    "wayve": "scaleup",
    "mercury": "scaleup",
    "hightouch": "scaleup",
    "cohere": "scaleup",
    "perplexity": "scaleup",
    "lambda": "scaleup",
    "togetherai": "scaleup",
    "hebbia": "scaleup",
    "langchain": "scaleup",
    "astranis": "scaleup",
    "marshmallow": "scaleup",
    "wheely": "scaleup",
    "glossgenius": "scaleup",
    "labelbox": "scaleup",
    "growtherapy": "scaleup",
    "tripledot": "scaleup",
    "goodnotes": "scaleup",

    # Scaleups that should be Enterprise (500+ employees)
    "affirm": "enterprise",
    "reddit": "enterprise",
    "anthropic": "enterprise",
    "discord": "enterprise",
    "airtable": "enterprise",
    "gitlab": "enterprise",
    "monzo": "enterprise",
    "wise": "enterprise",
    "figma": "enterprise",
    "duolingo": "enterprise",
    "grammarly": "enterprise",
    "checkr": "enterprise",
    "braze": "enterprise",
    "plaid": "enterprise",
    "asana": "enterprise",
    "doordash": "enterprise",
    "gusto": "enterprise",
    "pleo": "enterprise",
    "wiz": "enterprise",
    "intercom": "enterprise",
    "miro": "enterprise",
    "scale": "enterprise",
    "rippling": "enterprise",
    "tripadvisor": "enterprise",
    "deliveroo": "enterprise",
    "roku": "enterprise",
    "sofi": "enterprise",
    "andurilindustries": "enterprise",
    "aurorainnovation": "enterprise",
    "handshake": "enterprise",
    "kraken": "enterprise",
    "gemini": "enterprise",
    "rubrik": "enterprise",
    "flexport": "enterprise",
    "faire": "enterprise",
    "motive": "enterprise",
    "attentive": "enterprise",
    "abnormalsecurity": "enterprise",
    "gocardless": "enterprise",
    "octoenergy": "enterprise",
    "webflow": "enterprise",
    "vanta": "enterprise",
    "glean": "enterprise",
    "moloco": "enterprise",
    "skyscanner": "enterprise",
    "whatnot": "enterprise",

    # Null values that should be classified
    "netskope": "enterprise",
    "aristocrat technologies": "enterprise",
    "vontier": "enterprise",
    "corpay": "enterprise",
    "astreya": "enterprise",
    "kforce": "enterprise",
    "encora": "enterprise",
    "imanage": "enterprise",
    "kharon": "scaleup",
}

# Recruitment agencies to exclude (delete from employer_metadata)
AGENCIES_TO_EXCLUDE = [
    "ef recruitment",
    "red global",
    "cymertek",
    "zone it solutions",
    "technopride ltd",
    "kavaliro",
    "randstad technologies recruitment",
    "arthur recruitment",
    "pioneer search",
    "suncap technology",
    "redline group ltd",
    "concept resourcing",
    "altamira",
    "mm international",
    "cella",
    "aston carter",
    "online remote jobs",
    "atlas search",
    "mitchell maguire",
    "engineering employment",
    "carrington recruitment solutions limited",
    "akaasa technologies",
    "cella inc",
    "gliacell technologies",
    "kellymitchell group",
    "si solutions, llc",
    "travelnursesource",
    "n consulting ltd",
    "diverse lynx",
    "lynx recruitment ltd",
    "lynx recruitment",
    "prospero integrated",
    "elliot partnership",
    "talencia",
    "actalent",
    "randstad technologies",
    "wyetech",
    "tech aalto",
    "drc systems",
    "mindlance",
    "formula recruitment",
    "mackay sposito",
    "vdart inc",
    "seacare manpower services pte ltd",
    "rapsys technologies pte ltd.",
    "unison group",
    "falcon green personnel",
    "goodman masson",
    "resolvesoft inc",
    "techohana",
    "indigo tg",
    "appic solutions",
    "computer futures",
    "eligo recruitment ltd",
    "microtech global ltd",
    "xcellink pte ltd",
    "sphere digital recruitment",
    "pyramid etc companies, llc",
    "catapult solutions group",
    "mindbank consulting group",
    "harvey nash",
    "quality talent group",
    "us tech solutions, inc.",
    "veerteq solutions inc.",
    "purple drive",
    "interex group",
    "morgan mckinley",
    "talent international uk ltd",
    "jacobs massey",
    "blank space recruitment",
    "skilled careers ltd",
    "pri technology",
    "shulman fleming & partners",
    "magnet medical",
    "staffworx limited",
    "achieving stars therapy",
    "summer browning associates",
]


def apply_size_corrections(dry_run: bool = True) -> dict:
    """Apply employer_size corrections to employer_metadata table."""
    results = {"updated": 0, "not_found": [], "errors": []}

    for canonical_name, new_size in SIZE_CORRECTIONS.items():
        try:
            if dry_run:
                # Check if record exists
                check = supabase.table("employer_metadata").select("canonical_name, employer_size").eq("canonical_name", canonical_name).execute()
                if check.data:
                    old_size = check.data[0].get("employer_size", "null")
                    print(f"[DRY RUN] Would update '{canonical_name}': {old_size} -> {new_size}")
                    results["updated"] += 1
                else:
                    print(f"[DRY RUN] Not found: '{canonical_name}'")
                    results["not_found"].append(canonical_name)
            else:
                response = supabase.table("employer_metadata").update(
                    {"employer_size": new_size}
                ).eq("canonical_name", canonical_name).execute()

                if response.data:
                    print(f"[UPDATED] '{canonical_name}' -> {new_size}")
                    results["updated"] += 1
                else:
                    print(f"[NOT FOUND] '{canonical_name}'")
                    results["not_found"].append(canonical_name)

        except Exception as e:
            print(f"[ERROR] '{canonical_name}': {e}")
            results["errors"].append((canonical_name, str(e)))

    return results


def exclude_agencies(dry_run: bool = True) -> dict:
    """Delete recruitment agencies from employer_metadata table."""
    results = {"deleted": 0, "not_found": [], "errors": []}

    for agency_name in AGENCIES_TO_EXCLUDE:
        try:
            if dry_run:
                # Check if record exists
                check = supabase.table("employer_metadata").select("canonical_name").eq("canonical_name", agency_name).execute()
                if check.data:
                    print(f"[DRY RUN] Would delete agency: '{agency_name}'")
                    results["deleted"] += 1
                else:
                    # Agency might not be in employer_metadata (only in enriched_jobs)
                    results["not_found"].append(agency_name)
            else:
                response = supabase.table("employer_metadata").delete().eq("canonical_name", agency_name).execute()

                if response.data:
                    print(f"[DELETED] Agency: '{agency_name}'")
                    results["deleted"] += 1
                else:
                    results["not_found"].append(agency_name)

        except Exception as e:
            print(f"[ERROR] '{agency_name}': {e}")
            results["errors"].append((agency_name, str(e)))

    return results


def main():
    parser = argparse.ArgumentParser(description="Apply employer size corrections")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--apply", action="store_true", help="Apply changes to database")
    parser.add_argument("--corrections-only", action="store_true", help="Only apply size corrections, skip agency exclusions")
    parser.add_argument("--exclusions-only", action="store_true", help="Only delete agencies, skip size corrections")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Error: Must specify --dry-run or --apply")
        print("Usage: python apply_employer_size_corrections.py --dry-run")
        return

    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "APPLYING CHANGES"
    print(f"\n{'='*60}")
    print(f"  Employer Size Corrections - {mode}")
    print(f"{'='*60}\n")

    # Apply size corrections
    if not args.exclusions_only:
        print("--- SIZE CORRECTIONS ---\n")
        correction_results = apply_size_corrections(dry_run)
        print(f"\nSize corrections: {correction_results['updated']} updated, {len(correction_results['not_found'])} not found")

    # Exclude agencies
    if not args.corrections_only:
        print("\n--- AGENCY EXCLUSIONS ---\n")
        exclusion_results = exclude_agencies(dry_run)
        print(f"\nAgency exclusions: {exclusion_results['deleted']} deleted, {len(exclusion_results['not_found'])} not found")

    print(f"\n{'='*60}")
    if dry_run:
        print("  DRY RUN COMPLETE - No changes made")
        print("  Run with --apply to execute changes")
    else:
        print("  CHANGES APPLIED SUCCESSFULLY")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
