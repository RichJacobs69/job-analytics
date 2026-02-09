"""
Cleanup salary data: remove unreliable salary entries.

Three categories of bad salary data:
1. Adzuna (all cities) - "predicted" salaries are Adzuna's own model estimates,
   "actual" salaries are mostly agency-posted figures. Neither is structured employer data.
2. London (all sources) - no pay transparency laws, classifier-extracted salary is not trustworthy.
3. Singapore (all sources) - no pay transparency laws, classifier-extracted salary is not trustworthy.

Usage:
    python pipeline/utilities/cleanup_salary_data.py --dry-run    # Preview affected rows
    python pipeline/utilities/cleanup_salary_data.py              # Apply cleanup
"""

import os
import argparse
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

BATCH_SIZE = 1000


def count_salary_rows(supabase, filters: dict) -> int:
    """Count rows with non-null salary matching the given filters (paginated to avoid timeout)."""
    return len(fetch_ids_with_salary(supabase, filters))


def fetch_ids_with_salary(supabase, filters: dict) -> list:
    """Fetch all IDs with non-null salary matching the given filters, with pagination."""
    all_ids = []
    offset = 0
    while True:
        query = (
            supabase.table('enriched_jobs')
            .select('id')
            .not_.is_('salary_min', 'null')
        )
        for field, value in filters.items():
            query = query.eq(field, value)
        batch = query.range(offset, offset + BATCH_SIZE - 1).execute()
        if not batch.data:
            break
        all_ids.extend(row['id'] for row in batch.data)
        if len(batch.data) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return all_ids


def null_salary_for_ids(supabase, ids: list, label: str):
    """Null out salary fields for a list of IDs, in batches."""
    success = 0
    errors = 0
    for i in range(0, len(ids), BATCH_SIZE):
        batch_ids = ids[i:i + BATCH_SIZE]
        try:
            supabase.table('enriched_jobs').update({
                'currency': None,
                'salary_min': None,
                'salary_max': None,
            }).in_('id', batch_ids).execute()
            success += len(batch_ids)
        except Exception as e:
            errors += len(batch_ids)
            print(f'  [ERROR] {label} batch {i // BATCH_SIZE + 1}: {e}')

        if success % 5000 == 0 and success > 0:
            print(f'  {label}: {success}/{len(ids)} updated...')

    print(f'  {label}: {success} updated, {errors} errors')
    return success, errors


def main():
    parser = argparse.ArgumentParser(description='Cleanup unreliable salary data')
    parser.add_argument('--dry-run', action='store_true', help='Preview affected rows without updating')
    args = parser.parse_args()

    supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

    # --- Count affected rows ---
    print('Counting affected rows...\n')

    adzuna_count = count_salary_rows(supabase, {'data_source': 'adzuna'})
    london_count = count_salary_rows(supabase, {'city_code': 'lon'})
    singapore_count = count_salary_rows(supabase, {'city_code': 'sgp'})

    print(f'1. Adzuna (all cities):    {adzuna_count:,} rows with salary data')
    print(f'2. London (all sources):   {london_count:,} rows with salary data')
    print(f'3. Singapore (all sources): {singapore_count:,} rows with salary data')
    print(f'\nNote: Some rows overlap (e.g. Adzuna London jobs counted in both #1 and #2).')

    if args.dry_run:
        print(f'\n[DRY RUN] No changes applied. Run without --dry-run to apply.')
        return

    # --- Apply cleanup ---
    print(f'\n--- Applying cleanup ---\n')

    # 1. Adzuna
    print('Fetching Adzuna job IDs...')
    adzuna_ids = fetch_ids_with_salary(supabase, {'data_source': 'adzuna'})
    print(f'  Found {len(adzuna_ids):,} Adzuna jobs to clean')
    if adzuna_ids:
        null_salary_for_ids(supabase, adzuna_ids, 'Adzuna')

    # 2. London
    print('\nFetching London job IDs...')
    london_ids = fetch_ids_with_salary(supabase, {'city_code': 'lon'})
    print(f'  Found {len(london_ids):,} London jobs to clean')
    if london_ids:
        null_salary_for_ids(supabase, london_ids, 'London')

    # 3. Singapore
    print('\nFetching Singapore job IDs...')
    sgp_ids = fetch_ids_with_salary(supabase, {'city_code': 'sgp'})
    print(f'  Found {len(sgp_ids):,} Singapore jobs to clean')
    if sgp_ids:
        null_salary_for_ids(supabase, sgp_ids, 'Singapore')

    # --- Verify ---
    print(f'\n--- Verification ---\n')
    adzuna_after = count_salary_rows(supabase, {'data_source': 'adzuna'})
    london_after = count_salary_rows(supabase, {'city_code': 'lon'})
    sgp_after = count_salary_rows(supabase, {'city_code': 'sgp'})

    print(f'Adzuna salary rows remaining:    {adzuna_after:,}')
    print(f'London salary rows remaining:    {london_after:,}')
    print(f'Singapore salary rows remaining: {sgp_after:,}')

    print(f'\n[DONE] Salary cleanup complete.')


if __name__ == '__main__':
    main()
