"""
Backfill working_arrangement_default in employer_metadata table.

This script analyzes existing classified jobs and infers the default
working arrangement for each employer using majority vote.

Usage:
    python pipeline/utilities/backfill_working_arrangement_defaults.py --dry-run
    python pipeline/utilities/backfill_working_arrangement_defaults.py --apply
    python pipeline/utilities/backfill_working_arrangement_defaults.py --apply --employer "figma"

Algorithm:
    For each employer with NULL working_arrangement_default:
    1. Query enriched_jobs WHERE employer_name matches (case-insensitive)
    2. Count working_arrangement values (exclude 'unknown')
    3. If total known >= min_jobs AND top value >= threshold:
       - Set working_arrangement_default = top value
       - Set working_arrangement_source = 'inferred'
    4. Otherwise leave as NULL

Source Priority (never overwrite higher priority):
    1. manual (human verified)
    2. scraped (from career page - future)
    3. inferred (this script)
"""

import argparse
import sys
from pathlib import Path
from collections import Counter, defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.db_connection import supabase


# Source priority - lower number = higher priority
SOURCE_PRIORITY = {
    'manual': 1,
    'scraped': 2,
    'inferred': 3,
}


def get_working_arrangement_counts() -> dict[str, Counter]:
    """
    Query enriched_jobs and count working_arrangement by employer.
    Returns dict: canonical_name -> Counter of working_arrangements
    """
    print("Fetching working arrangement counts from enriched_jobs...")

    counts_by_employer = defaultdict(Counter)
    offset = 0
    batch_size = 1000
    total_rows = 0

    while True:
        response = supabase.table("enriched_jobs").select(
            "employer_name, working_arrangement"
        ).neq(
            "working_arrangement", "unknown"
        ).range(offset, offset + batch_size - 1).execute()

        if not response.data:
            break

        for row in response.data:
            employer = row["employer_name"].lower().strip()
            wa = row["working_arrangement"]
            counts_by_employer[employer][wa] += 1
            total_rows += 1

        offset += batch_size

        if len(response.data) < batch_size:
            break

    print(f"  Loaded {total_rows} jobs with known working_arrangement")
    print(f"  Found {len(counts_by_employer)} unique employers")

    return dict(counts_by_employer)


def get_employers_needing_inference() -> list[dict]:
    """
    Get employers from employer_metadata where working_arrangement_default is NULL
    or source is 'inferred' (can be re-inferred with more data).
    """
    print("Fetching employers needing inference...")

    employers = []
    offset = 0
    batch_size = 1000

    while True:
        response = supabase.table("employer_metadata").select(
            "canonical_name, display_name, working_arrangement_default, working_arrangement_source"
        ).range(offset, offset + batch_size - 1).execute()

        if not response.data:
            break

        for row in response.data:
            source = row.get("working_arrangement_source")
            current_default = row.get("working_arrangement_default")

            # Include if:
            # - No default set (NULL)
            # - Or source is 'inferred' (can be updated with more data)
            if current_default is None or source == 'inferred':
                employers.append(row)

        offset += batch_size

        if len(response.data) < batch_size:
            break

    print(f"  Found {len(employers)} employers eligible for inference")

    return employers


def compute_inference(
    counts: Counter,
    threshold: float = 0.7,
    min_jobs: int = 3
) -> tuple[str | None, float, int]:
    """
    Compute inferred working_arrangement from job counts.

    Returns:
        (inferred_value, confidence, total_jobs)
        - inferred_value: 'remote', 'hybrid', 'onsite', 'flexible', or None
        - confidence: percentage of jobs with the top value
        - total_jobs: total jobs with known working_arrangement
    """
    if not counts:
        return None, 0.0, 0

    total = sum(counts.values())

    if total < min_jobs:
        return None, 0.0, total

    # Get top value
    top_value, top_count = counts.most_common(1)[0]
    confidence = top_count / total

    if confidence >= threshold:
        return top_value, confidence, total
    else:
        return None, confidence, total


def apply_inference(
    canonical_name: str,
    inferred_value: str,
    dry_run: bool = True
) -> bool:
    """
    Update employer_metadata with inferred working_arrangement_default.
    Returns True if updated (or would update in dry-run).
    """
    if dry_run:
        return True

    try:
        response = supabase.table("employer_metadata").update({
            "working_arrangement_default": inferred_value,
            "working_arrangement_source": "inferred"
        }).eq("canonical_name", canonical_name).execute()

        return bool(response.data)

    except Exception as e:
        print(f"  [ERROR] Failed to update '{canonical_name}': {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Backfill working_arrangement_default using majority vote"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without applying"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply changes to database"
    )
    parser.add_argument(
        "--min-jobs", type=int, default=3,
        help="Minimum jobs with known arrangement (default: 3)"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.7,
        help="Agreement threshold (default: 0.7 = 70%%)"
    )
    parser.add_argument(
        "--employer", type=str, default=None,
        help="Process single employer only (canonical name)"
    )
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Error: Must specify --dry-run or --apply")
        print("Usage: python backfill_working_arrangement_defaults.py --dry-run")
        return 1

    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "APPLYING CHANGES"

    print(f"\n{'='*70}")
    print(f"  Working Arrangement Default Backfill - {mode}")
    print(f"  Threshold: {args.threshold*100:.0f}% | Min Jobs: {args.min_jobs}")
    print(f"{'='*70}\n")

    # Step 1: Get working arrangement counts from jobs
    counts_by_employer = get_working_arrangement_counts()

    # Step 2: Get employers needing inference
    employers = get_employers_needing_inference()

    # Filter to single employer if specified
    if args.employer:
        canonical = args.employer.lower().strip()
        employers = [e for e in employers if e["canonical_name"] == canonical]
        if not employers:
            print(f"Employer '{args.employer}' not found or not eligible for inference")
            return 1

    # Step 3: Process each employer
    results = {
        "updated_from_null": [],      # NULL -> inferred
        "updated_reinferred": [],     # inferred -> inferred (value changed)
        "updated_unchanged": [],      # inferred -> same value (no-op but still counts)
        "skipped_low_confidence": [],
        "skipped_no_data": [],
        "skipped_few_jobs": [],
        "errors": []
    }

    print("\n--- Processing Employers ---\n")

    for employer in employers:
        canonical = employer["canonical_name"]
        display = employer.get("display_name", canonical)
        previous_value = employer.get("working_arrangement_default")
        previous_source = employer.get("working_arrangement_source")
        counts = counts_by_employer.get(canonical, Counter())

        inferred, confidence, total = compute_inference(
            counts,
            threshold=args.threshold,
            min_jobs=args.min_jobs
        )

        if total == 0:
            results["skipped_no_data"].append(canonical)
            continue

        if total < args.min_jobs:
            results["skipped_few_jobs"].append((canonical, total))
            continue

        if inferred is None:
            # Threshold not met - show distribution for manual review
            dist = ", ".join(f"{k}:{v}" for k, v in counts.most_common())
            results["skipped_low_confidence"].append((canonical, confidence, total, dist))
            continue

        # Apply inference - show transition from previous state
        prefix = "[DRY RUN]" if dry_run else "[UPDATED]"
        if previous_value is None:
            transition = f"NULL -> {inferred}"
        elif previous_value == inferred:
            transition = f"{inferred} (unchanged)"
        else:
            transition = f"{previous_value} -> {inferred}"
        print(f"{prefix} {display}: {transition} ({confidence*100:.0f}% of {total} jobs)")

        if apply_inference(canonical, inferred, dry_run):
            # Track which type of update this was
            if previous_value is None:
                results["updated_from_null"].append((canonical, inferred, confidence, total))
            elif previous_value == inferred:
                results["updated_unchanged"].append((canonical, inferred, confidence, total))
            else:
                results["updated_reinferred"].append((canonical, previous_value, inferred, confidence, total))
        else:
            results["errors"].append(canonical)

    # Step 4: Print summary
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}\n")

    total_updated = len(results['updated_from_null']) + len(results['updated_reinferred']) + len(results['updated_unchanged'])
    print(f"Updated: {total_updated}")
    print(f"  - NULL -> inferred: {len(results['updated_from_null'])}")
    print(f"  - Re-inferred (value changed): {len(results['updated_reinferred'])}")
    print(f"  - Re-inferred (unchanged): {len(results['updated_unchanged'])}")
    print(f"Skipped (low confidence <{args.threshold*100:.0f}%): {len(results['skipped_low_confidence'])}")
    print(f"Skipped (no data): {len(results['skipped_no_data'])}")
    print(f"Skipped (< {args.min_jobs} jobs): {len(results['skipped_few_jobs'])}")
    print(f"Errors: {len(results['errors'])}")

    # Show re-inferred changes if any
    if results['updated_reinferred']:
        print(f"\n--- Re-inferred Value Changes ({len(results['updated_reinferred'])}) ---")
        for canonical, old_val, new_val, conf, total in results['updated_reinferred']:
            print(f"  {canonical}: {old_val} -> {new_val} ({conf*100:.0f}% of {total} jobs)")

    # Show low-confidence employers for manual review
    if results["skipped_low_confidence"]:
        print(f"\n--- Employers Needing Manual Review ({len(results['skipped_low_confidence'])}) ---")
        print("(Threshold not met - requires human verification)\n")

        # Sort by total jobs descending
        sorted_lc = sorted(results["skipped_low_confidence"], key=lambda x: -x[2])

        for canonical, confidence, total, dist in sorted_lc[:20]:  # Top 20
            print(f"  {canonical}: {confidence*100:.0f}% ({total} jobs) - {dist}")

        if len(results["skipped_low_confidence"]) > 20:
            print(f"  ... and {len(results['skipped_low_confidence']) - 20} more")

    print(f"\n{'='*70}")
    if dry_run:
        print("  DRY RUN COMPLETE - No changes made")
        print("  Run with --apply to execute changes")
    else:
        print("  BACKFILL COMPLETE")
    print(f"{'='*70}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
