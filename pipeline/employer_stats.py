"""
Employer Fill Stats Generator
Computes median fill time per employer for user-facing context in job feed.

Part of: EPIC-008 Curated Job Feed
Runs: Nightly via GitHub Actions (after url_validator.py completes)

Logic:
- "Closed" role = url_status in ('404', '410', 'soft_404') - definitively closed
- Fill time = days between posted_date and url_checked_at (when dead link was detected)
- Median fill time = informational metric for users, not a filter criterion
- Minimum sample size = 3 (for meaningful statistics)
"""

import sys
sys.path.insert(0, '.')

from datetime import datetime
from collections import defaultdict
import statistics
from pipeline.db_connection import supabase


def compute_employer_fill_stats(dry_run: bool = False):
    """
    Compute median fill times per employer and upsert to employer_fill_stats table.

    Uses 404/410/soft_404 as definitive signals that a job is closed.
    Fill time = posted_date to url_checked_at (when dead link was detected).

    Args:
        dry_run: If True, show what would be computed without updating database
    """
    print("=" * 70)
    print("EMPLOYER FILL STATS GENERATOR")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Dry run: {dry_run}")
    print()

    # Step 1: Fetch closed roles (url_status = '404', '410', or 'soft_404')
    print("[DATA] Fetching closed roles (url_status = 404/410/soft_404)...")

    try:
        closed_roles = []
        offset = 0
        page_size = 1000

        while True:
            result = supabase.table("enriched_jobs") \
                .select("employer_name, posted_date, url_checked_at") \
                .in_("data_source", ["greenhouse", "lever", "ashby"]) \
                .in_("url_status", ["404", "410", "soft_404"]) \
                .not_.is_("url_checked_at", "null") \
                .range(offset, offset + page_size - 1) \
                .execute()

            if not result.data:
                break

            closed_roles.extend(result.data)
            print(f"   [PAGE] Fetched {len(result.data)} roles (total: {len(closed_roles)})")

            if len(result.data) < page_size:
                break
            offset += page_size

        print(f"[OK] Found {len(closed_roles)} confirmed closed roles (404/410/soft_404)")

        if not closed_roles:
            print("\n[WARN] No closed roles found. Run url_validator.py first to detect dead links.")
            return

    except Exception as e:
        print(f"[ERROR] Failed to fetch closed roles: {e}")
        return

    # Step 2: Group by employer (canonical_name = lowercase) and compute fill times
    print("\n[COMPUTE] Computing fill times per employer (using canonical names)...")

    employer_fill_days = defaultdict(list)

    for role in closed_roles:
        employer = role['employer_name']
        if not employer:
            continue

        # Normalize to canonical_name (lowercase)
        canonical_name = employer.lower().strip()

        try:
            posted = datetime.strptime(role['posted_date'], '%Y-%m-%d')
            # url_checked_at is when we detected the 404
            checked_at = role['url_checked_at']
            if isinstance(checked_at, str):
                # Handle ISO format with timezone
                checked = datetime.fromisoformat(checked_at.replace('Z', '+00:00')).replace(tzinfo=None)
            else:
                continue

            fill_days = (checked.date() - posted.date()).days

            # Sanity check: fill time should be positive and reasonable
            if 0 < fill_days < 365:
                employer_fill_days[canonical_name].append(fill_days)
        except (ValueError, TypeError) as e:
            continue

    print(f"[OK] Computed fill times for {len(employer_fill_days)} employers")

    # Step 3: Compute median for employers with sufficient sample size
    print("\n[STATS] Computing median fill times (min sample size: 3)...")

    employer_stats = []
    insufficient_sample = 0

    for canonical_name, fill_days in employer_fill_days.items():
        sample_size = len(fill_days)

        if sample_size >= 3:
            median_days = statistics.median(fill_days)
            employer_stats.append({
                'canonical_name': canonical_name,
                'median_days_to_fill': round(median_days, 1),
                'sample_size': sample_size
            })
        else:
            insufficient_sample += 1

    # Sort by sample size for display
    employer_stats.sort(key=lambda x: x['sample_size'], reverse=True)

    print(f"[OK] {len(employer_stats)} employers have sufficient data (3+ closed roles)")
    print(f"[SKIP] {insufficient_sample} employers have <3 closed roles")

    # Step 4: Show top employers
    print("\n[PREVIEW] Top 15 employers by sample size:")
    print("-" * 60)
    print(f"{'Canonical Name':<35} {'Median Days':>12} {'Sample':>8}")
    print("-" * 60)

    for stat in employer_stats[:15]:
        print(f"{stat['canonical_name'][:35]:<35} {stat['median_days_to_fill']:>12.1f} {stat['sample_size']:>8}")

    if len(employer_stats) > 15:
        print(f"... and {len(employer_stats) - 15} more employers")

    # Step 5: Upsert to database
    if dry_run:
        print("\n[DRY RUN] Would upsert {len(employer_stats)} employer stats")
        return

    print(f"\n[DB] Upserting {len(employer_stats)} employer stats...")

    try:
        upserted = 0
        errors = 0

        for stat in employer_stats:
            try:
                supabase.table("employer_fill_stats") \
                    .upsert({
                        'canonical_name': stat['canonical_name'],
                        'median_days_to_fill': stat['median_days_to_fill'],
                        'sample_size': stat['sample_size'],
                        'computed_at': datetime.now().isoformat()
                    }, on_conflict='canonical_name') \
                    .execute()
                upserted += 1
            except Exception as e:
                print(f"   [ERROR] Failed to upsert {stat['canonical_name']}: {e}")
                errors += 1

        print(f"[OK] Upserted: {upserted}, Errors: {errors}")

    except Exception as e:
        print(f"[ERROR] Database upsert failed: {e}")
        return

    # Step 6: Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Closed roles analyzed: {len(closed_roles)}")
    print(f"Employers with stats: {len(employer_stats)}")
    print(f"Employers skipped (low sample): {insufficient_sample}")

    if employer_stats:
        all_medians = [s['median_days_to_fill'] for s in employer_stats]
        print(f"\nMedian fill time distribution:")
        print(f"  Min: {min(all_medians):.1f} days")
        print(f"  Max: {max(all_medians):.1f} days")
        print(f"  Overall median: {statistics.median(all_medians):.1f} days")

    print("\n[DONE] Employer fill stats generation complete!")


def verify_stats():
    """Verify employer_fill_stats table contents."""
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    try:
        result = supabase.table("employer_fill_stats") \
            .select("*") \
            .order("sample_size", desc=True) \
            .limit(20) \
            .execute()

        print(f"\nTop 20 employers by sample size:")
        print("-" * 70)
        print(f"{'Canonical Name':<35} {'Median Days':>12} {'Sample':>8} {'Computed':<15}")
        print("-" * 70)

        for row in result.data:
            computed = row['computed_at'][:10] if row['computed_at'] else 'N/A'
            # Handle both old (employer_name) and new (canonical_name) column names
            name = row.get('canonical_name') or row.get('employer_name', 'unknown')
            print(f"{name[:35]:<35} {row['median_days_to_fill']:>12.1f} {row['sample_size']:>8} {computed:<15}")

        # Get total count
        count_result = supabase.table("employer_fill_stats") \
            .select("id", count='exact') \
            .execute()

        print(f"\nTotal employers with fill stats: {count_result.count}")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv or "-d" in sys.argv
    verify_only = "--verify" in sys.argv or "-v" in sys.argv

    if verify_only:
        verify_stats()
    else:
        compute_employer_fill_stats(dry_run=dry_run)
        verify_stats()

    print("\n" + "=" * 70)
    print("USAGE:")
    print("  python pipeline/employer_stats.py              # Compute and upsert stats")
    print("  python pipeline/employer_stats.py --dry-run    # Preview without updating")
    print("  python pipeline/employer_stats.py --verify     # Just check current state")
    print("=" * 70)
