"""
Backfill track and seniority for delivery and product roles.

Fixes two classifier issues caused by "Manager" in titles:
1. Track: Programme/Project/Product Managers classified as 'management' when they're IC
2. Seniority: Same roles classified as 'director_plus' without Director/Head/VP signal

Heuristic:
- If title contains Director|Head|VP|Chief|SVP|EVP|AVP|RVP|Partner -> keep management + director_plus
- Otherwise -> set track=ic, and fix seniority based on title level qualifiers

Usage:
    python pipeline/utilities/backfill_track_seniority.py --dry-run    # Preview changes
    python pipeline/utilities/backfill_track_seniority.py              # Apply changes
"""

import os
import re
import argparse
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

# Patterns that indicate genuine director_plus / management roles
DIRECTOR_PATTERNS = [
    r'\bdirector\b',
    r'\bhead of\b',
    r'\bhead,',
    r'\bvp\b',
    r'\bvice president\b',
    r'\bsvp\b',
    r'\bevp\b',
    r'\bavp\b',
    r'\brvp\b',
    r'\bchief\b',
    r'\bcto\b',
    r'\bcpo\b',
    r'\bcdo\b',
    r'\bpartner\b',
]

# Patterns for seniority reclassification (IC scale)
STAFF_PATTERNS = [r'\bstaff\b', r'\bprincipal\b']
SENIOR_PATTERNS = [r'\bsenior\b', r'\bsr\.?\b', r'\blead\b']


def has_director_signal(title: str) -> bool:
    """Check if title contains a director_plus keyword."""
    title_lower = title.lower()
    return any(re.search(p, title_lower) for p in DIRECTOR_PATTERNS)


def infer_seniority(title: str) -> str:
    """Infer correct seniority from title using IC scale."""
    title_lower = title.lower()
    if any(re.search(p, title_lower) for p in STAFF_PATTERNS):
        return 'staff_principal'
    if any(re.search(p, title_lower) for p in SENIOR_PATTERNS):
        return 'senior'
    return 'mid'


def fetch_candidates(supabase, job_family: str, field: str, value: str) -> list:
    """Fetch all non-agency jobs matching family + field=value with pagination."""
    all_jobs = []
    offset = 0
    while True:
        batch = (
            supabase.table('enriched_jobs')
            .select('id, title_display, title_canonical, job_subfamily, seniority, track, data_source')
            .eq('job_family', job_family)
            .eq(field, value)
            .eq('is_agency', False)
            .range(offset, offset + 999)
            .execute()
        )
        if not batch.data:
            break
        all_jobs.extend(batch.data)
        offset += 1000
        if len(batch.data) < 1000:
            break
    return all_jobs


def get_title(job: dict) -> str:
    """Get title from job record."""
    return job.get('title_display') or job.get('title_canonical') or ''


def main():
    parser = argparse.ArgumentParser(description='Backfill track and seniority for delivery/product roles')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    args = parser.parse_args()

    supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

    track_updates = []  # (id, old_track, new_track, title)
    seniority_updates = []  # (id, old_seniority, new_seniority, title)

    for family in ['delivery', 'product']:
        # --- Fix 1: track=management -> ic where no director signal ---
        mgmt_jobs = fetch_candidates(supabase, family, 'track', 'management')
        for job in mgmt_jobs:
            title = get_title(job)
            if not has_director_signal(title):
                track_updates.append((job['id'], 'management', 'ic', title, family))

        # --- Fix 2: seniority=director_plus -> correct level where no director signal ---
        dp_jobs = fetch_candidates(supabase, family, 'seniority', 'director_plus')
        for job in dp_jobs:
            title = get_title(job)
            if not has_director_signal(title):
                new_seniority = infer_seniority(title)
                seniority_updates.append((job['id'], 'director_plus', new_seniority, title, family))

    # --- Report ---
    print(f'Track updates (management -> ic): {len(track_updates)}')
    delivery_track = sum(1 for u in track_updates if u[4] == 'delivery')
    product_track = sum(1 for u in track_updates if u[4] == 'product')
    print(f'  Delivery: {delivery_track}')
    print(f'  Product:  {product_track}')

    print(f'\nSeniority updates (director_plus -> correct level): {len(seniority_updates)}')
    delivery_sen = sum(1 for u in seniority_updates if u[4] == 'delivery')
    product_sen = sum(1 for u in seniority_updates if u[4] == 'product')
    print(f'  Delivery: {delivery_sen}')
    print(f'  Product:  {product_sen}')

    # Seniority remap breakdown
    from collections import Counter
    remap = Counter(u[2] for u in seniority_updates)
    print(f'\n  Seniority remap breakdown:')
    for level, count in remap.most_common():
        print(f'    -> {level}: {count}')

    # Show samples
    print(f'\n--- Sample track updates (first 10) ---')
    for job_id, old, new, title, family in track_updates[:10]:
        print(f'  [{family:<8}] {title[:70]}  ({old} -> {new})')

    print(f'\n--- Sample seniority updates (first 10) ---')
    for job_id, old, new, title, family in seniority_updates[:10]:
        print(f'  [{family:<8}] {title[:70]}  ({old} -> {new})')

    if args.dry_run:
        print(f'\n[DRY RUN] No changes applied. Run without --dry-run to apply.')
        return

    # --- Apply updates ---
    print(f'\nApplying track updates...')
    track_success = 0
    track_errors = 0
    for job_id, old, new, title, family in track_updates:
        try:
            supabase.table('enriched_jobs').update({'track': new}).eq('id', job_id).execute()
            track_success += 1
        except Exception as e:
            track_errors += 1
            if track_errors <= 5:
                print(f'  [ERROR] {job_id}: {e}')

        if track_success % 200 == 0 and track_success > 0:
            print(f'  Track: {track_success}/{len(track_updates)} updated...')

    print(f'  Track: {track_success} updated, {track_errors} errors')

    print(f'\nApplying seniority updates...')
    sen_success = 0
    sen_errors = 0
    for job_id, old, new, title, family in seniority_updates:
        try:
            supabase.table('enriched_jobs').update({'seniority': new}).eq('id', job_id).execute()
            sen_success += 1
        except Exception as e:
            sen_errors += 1
            if sen_errors <= 5:
                print(f'  [ERROR] {job_id}: {e}')

        if sen_success % 200 == 0 and sen_success > 0:
            print(f'  Seniority: {sen_success}/{len(seniority_updates)} updated...')

    print(f'  Seniority: {sen_success} updated, {sen_errors} errors')

    print(f'\n[DONE] Backfill complete.')
    print(f'  Track:     {track_success} updated')
    print(f'  Seniority: {sen_success} updated')


if __name__ == '__main__':
    main()
