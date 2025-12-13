"""
Backfill Skill Family Code Rename
==================================
Updates existing enriched_jobs records to rename skill family codes.
In this case: analytics_pm → product_usage

Usage:
    python backfill_skill_family_rename.py [--dry-run]

Options:
    --dry-run   Show what would be updated without making changes
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client

load_dotenv()


def get_supabase():
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in environment")
    return create_client(url, key)


def backfill_skill_family_rename(old_code: str, new_code: str, dry_run: bool = False):
    """
    Rename skill family codes in all enriched_jobs records.

    Args:
        old_code: Old family code to find
        new_code: New family code to replace with
        dry_run: If True, don't actually update the database
    """
    supabase = get_supabase()

    print(f"Fetching records with skills containing family_code='{old_code}'...")

    # Fetch all records with skills
    query = supabase.table("enriched_jobs").select("id, skills")

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

    print(f"Found {len(all_records)} records total")

    # Track statistics
    stats = {
        "total_records": len(all_records),
        "records_with_skills": 0,
        "family_codes_updated": 0,
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
            family_code = skill.get("family_code")

            if family_code == old_code:
                stats["family_codes_updated"] += 1
                needs_update = True
                updated_skills.append({
                    "name": skill.get("name"),
                    "family_code": new_code
                })
            else:
                updated_skills.append(skill)

        if needs_update:
            updates.append({
                "id": job_id,
                "skills": updated_skills
            })

    print(f"\nStatistics:")
    print(f"  Records with skills: {stats['records_with_skills']}")
    print(f"  Family codes to update: {stats['family_codes_updated']}")
    print(f"  Records needing update: {len(updates)}")

    if dry_run:
        print(f"\n[DRY RUN] No changes made")
        if updates:
            print(f"\nSample updates (first 3):")
            for update in updates[:3]:
                print(f"  Job ID {update['id']}: {len(update['skills'])} skills")
                for skill in update["skills"][:5]:
                    if skill['family_code'] == new_code:
                        print(f"    - {skill['name']} -> {skill['family_code']} (UPDATED)")
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

        print(f"\nDone! Updated {stats['records_updated']} records")

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill skill family code rename")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes")
    args = parser.parse_args()

    backfill_skill_family_rename(
        old_code="analytics_pm",
        new_code="product_usage",
        dry_run=args.dry_run
    )
