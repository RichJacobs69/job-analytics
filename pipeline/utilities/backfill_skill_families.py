"""
Backfill Skill Family Codes
============================
Updates existing enriched_jobs records with skill family codes
using the deterministic skill_family_mapper.

Usage:
    python pipeline/utilities/backfill_skill_families.py [--dry-run] [--limit N] [--stats-only]

Options:
    --dry-run     Show what would be updated without making changes
    --limit N     Process only N records (for testing)
    --stats-only  Print mapping stats without querying DB
"""

import os
import argparse
from dotenv import load_dotenv
from supabase import create_client

from pipeline.skill_family_mapper import get_skill_family, get_canonical_name, get_mapping_stats

load_dotenv()


def get_supabase():
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in environment")
    return create_client(url, key)


def backfill_skill_families(dry_run: bool = False, limit: int = None):
    """
    Backfill skill family codes for all enriched_jobs records.

    Args:
        dry_run: If True, don't actually update the database
        limit: Maximum number of records to process
    """
    supabase = get_supabase()

    print("Fetching records with skills...")

    # Fetch all records with skills
    query = supabase.table("enriched_jobs").select("id, skills")

    if limit:
        query = query.limit(limit)

    # Paginate through all results
    all_records = []
    offset = 0
    page_size = 1000

    while True:
        result = query.range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        all_records.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
        if limit and len(all_records) >= limit:
            all_records = all_records[:limit]
            break

    print(f"Found {len(all_records)} records")

    # Track statistics
    stats = {
        "total_records": len(all_records),
        "records_with_skills": 0,
        "skills_updated": 0,
        "skills_name_fixed": 0,
        "skills_already_mapped": 0,
        "skills_unmapped": 0,
        "records_updated": 0,
    }

    updates = []

    for record in all_records:
        job_id = record["id"]
        skills = record.get("skills")

        if not skills or not isinstance(skills, list):
            continue

        stats["records_with_skills"] += 1
        needs_update = False
        updated_skills = []

        for skill in skills:
            name = skill.get("name", "")
            current_family = skill.get("family_code")
            canonical = get_canonical_name(name)
            new_family = get_skill_family(name)

            # Detect name casing change
            if canonical != name:
                stats["skills_name_fixed"] += 1
                needs_update = True

            if new_family:
                if current_family != new_family:
                    stats["skills_updated"] += 1
                    needs_update = True
                else:
                    stats["skills_already_mapped"] += 1
                updated_skills.append({"name": canonical, "family_code": new_family})
            else:
                stats["skills_unmapped"] += 1
                updated_skills.append({"name": canonical, "family_code": None})

        if needs_update:
            updates.append({"id": job_id, "skills": updated_skills})

    print(f"\nStatistics:")
    print(f"  Records with skills: {stats['records_with_skills']}")
    print(f"  Skills family updated: {stats['skills_updated']}")
    print(f"  Skills name casing fixed: {stats['skills_name_fixed']}")
    print(f"  Skills already correct: {stats['skills_already_mapped']}")
    print(f"  Skills unmapped (no mapping exists): {stats['skills_unmapped']}")
    print(f"  Records needing update: {len(updates)}")

    if dry_run:
        print("\n[DRY RUN] No changes made")
        if updates:
            print("\nSample updates (first 3):")
            for update in updates[:3]:
                print(f"  Job ID {update['id']}: {len(update['skills'])} skills")
                for skill in update["skills"][:5]:
                    print(f"    - {skill['name']} -> {skill['family_code']}")
        return stats

    # Apply updates in batches
    if updates:
        print(f"\nApplying {len(updates)} updates...")
        batch_size = 100
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            for update in batch:
                try:
                    supabase.table("enriched_jobs").update(
                        {"skills": update["skills"]}
                    ).eq("id", update["id"]).execute()
                    stats["records_updated"] += 1
                except Exception as e:
                    print(f"  Error updating job {update['id']}: {e}")

            print(f"  Progress: {min(i + batch_size, len(updates))}/{len(updates)}")

        print(f"\n[DONE] Updated {stats['records_updated']} records")

    return stats


def print_stats_only():
    """Print mapping stats without querying the database."""
    stats = get_mapping_stats()
    print("Skill Family Mapper Statistics")
    print("=" * 50)
    print(f"Total skills mapped: {stats['total_skills_mapped']}")
    print(f"Number of families: {stats['families']}")
    print()
    print("Skills per family:")
    for family, count in sorted(stats["skills_per_family"].items(), key=lambda x: -x[1]):
        print(f"  {family}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill skill family codes")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes")
    parser.add_argument("--limit", type=int, help="Limit records to process")
    parser.add_argument("--stats-only", action="store_true",
                        help="Print mapping stats without querying DB")
    args = parser.parse_args()

    if args.stats_only:
        print_stats_only()
    else:
        backfill_skill_families(dry_run=args.dry_run, limit=args.limit)
