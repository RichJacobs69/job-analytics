"""
Re-classify jobs with Gemini 3 Flash.

This utility re-runs classification on specific jobs that were misclassified
by older models (e.g., Gemini 2.5 Flash-Lite).

Usage:
    python pipeline/utilities/reclassify_jobs.py --raw-ids 30335,30433,30311
    python pipeline/utilities/reclassify_jobs.py --raw-ids-file ids.txt
    python pipeline/utilities/reclassify_jobs.py --find-engineering-misclassified
"""
import os
import sys
import json
import argparse
import time
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv()

from supabase import create_client
from pipeline.classifier import classify_job_with_gemini_retry as classify_job_with_gemini
from pipeline.job_family_mapper import get_correct_job_family


def get_supabase():
    return create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))


def find_engineering_misclassified_as_product():
    """Find all engineering roles incorrectly classified as product."""
    supabase = get_supabase()

    engineering_patterns = [
        '%Software Engineer%',
        '%Engineering Manager%',
        '%Product Engineer%',
        '%Platform Engineer%',
        '%AI Engineer%',
        '%ML Engineer%',
        '%SWE%',
        '%Developer%',
        '%Programmatic%',
        '%Manager, Product Engineering%',
    ]

    all_ids = set()

    for pattern in engineering_patterns:
        result = supabase.table('enriched_jobs').select(
            'id, raw_job_id, title_display'
        ).eq('job_family', 'product').ilike('title_display', pattern).execute()

        for job in result.data:
            title = job['title_display'].lower()
            # Skip actual PM roles
            if 'product manager' in title or 'product owner' in title:
                continue
            if ('pm' in title or 'gpm' in title) and 'developer' in title:
                continue
            all_ids.add(job['raw_job_id'])

    return sorted(all_ids)


def reclassify_job(raw_job_id: int, dry_run: bool = False, verbose: bool = False):
    """Re-classify a single job and update the database."""
    supabase = get_supabase()

    # Get raw job
    raw = supabase.table('raw_jobs').select('id, raw_text, title, company').eq('id', raw_job_id).execute()
    if not raw.data:
        return {'status': 'error', 'message': f'Raw job {raw_job_id} not found'}

    raw_job = raw.data[0]
    if not raw_job['raw_text']:
        return {'status': 'error', 'message': f'Raw job {raw_job_id} has no text'}

    # Get current enriched job
    enriched = supabase.table('enriched_jobs').select('*').eq('raw_job_id', raw_job_id).execute()
    if not enriched.data:
        return {'status': 'error', 'message': f'No enriched job for raw_job_id {raw_job_id}'}

    current = enriched.data[0]
    old_family = current['job_family']
    old_subfamily = current['job_subfamily']

    # Re-classify with Gemini 3 Flash
    try:
        result = classify_job_with_gemini(raw_job['raw_text'], verbose=verbose)
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

    if 'error' in result:
        # Try to extract subfamily from partial JSON in error message
        import re
        error_msg = result.get('error', '')
        match = re.search(r'"job_subfamily":\s*"([^"]+)"', error_msg)
        if match:
            # Recovered subfamily from partial JSON
            result = {'role': {'job_subfamily': match.group(1)}}
        else:
            return {'status': 'error', 'message': result['error']}

    # Extract new classification
    new_subfamily = result.get('role', {}).get('job_subfamily', 'out_of_scope')
    if new_subfamily == 'out_of_scope':
        new_family = 'out_of_scope'
    else:
        new_family = get_correct_job_family(new_subfamily) or 'out_of_scope'

    # Check if changed
    changed = (new_family != old_family) or (new_subfamily != old_subfamily)

    if not changed:
        return {
            'status': 'unchanged',
            'raw_job_id': raw_job_id,
            'title': raw_job['title'],
            'old': f'{old_family}/{old_subfamily}',
            'new': f'{new_family}/{new_subfamily}'
        }

    if dry_run:
        return {
            'status': 'would_update',
            'raw_job_id': raw_job_id,
            'title': raw_job['title'],
            'old': f'{old_family}/{old_subfamily}',
            'new': f'{new_family}/{new_subfamily}'
        }

    # Update enriched_jobs
    update_data = {
        'job_family': new_family,
        'job_subfamily': new_subfamily,
        'seniority': result.get('role', {}).get('seniority'),
        'track': result.get('role', {}).get('track'),
        'updated_at': datetime.utcnow().isoformat()
    }

    supabase.table('enriched_jobs').update(update_data).eq('raw_job_id', raw_job_id).execute()

    return {
        'status': 'updated',
        'raw_job_id': raw_job_id,
        'title': raw_job['title'],
        'old': f'{old_family}/{old_subfamily}',
        'new': f'{new_family}/{new_subfamily}'
    }


def main():
    parser = argparse.ArgumentParser(description='Re-classify jobs with Gemini 3 Flash')
    parser.add_argument('--raw-ids', type=str, help='Comma-separated list of raw_job_ids')
    parser.add_argument('--raw-ids-file', type=str, help='File containing raw_job_ids (one per line)')
    parser.add_argument('--find-engineering-misclassified', action='store_true',
                        help='Auto-find engineering roles misclassified as product')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')
    parser.add_argument('--verbose', action='store_true', help='Show detailed classification output')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of jobs to process (0 = no limit)')

    args = parser.parse_args()

    # Get raw_job_ids
    raw_ids = []

    if args.find_engineering_misclassified:
        print('Finding engineering roles misclassified as product...')
        raw_ids = find_engineering_misclassified_as_product()
        print(f'Found {len(raw_ids)} jobs to re-classify')
    elif args.raw_ids:
        raw_ids = [int(x.strip()) for x in args.raw_ids.split(',')]
    elif args.raw_ids_file:
        with open(args.raw_ids_file) as f:
            raw_ids = [int(line.strip()) for line in f if line.strip()]
    else:
        parser.print_help()
        return

    if args.limit > 0:
        raw_ids = raw_ids[:args.limit]

    print(f'\nProcessing {len(raw_ids)} jobs...')
    if args.dry_run:
        print('[DRY RUN - no changes will be made]\n')

    stats = {'updated': 0, 'unchanged': 0, 'error': 0, 'would_update': 0}

    for i, raw_id in enumerate(raw_ids):
        result = reclassify_job(raw_id, dry_run=args.dry_run, verbose=args.verbose)
        stats[result['status']] = stats.get(result['status'], 0) + 1

        status_marker = {
            'updated': '[UPDATED]',
            'would_update': '[WOULD UPDATE]',
            'unchanged': '[unchanged]',
            'error': '[ERROR]'
        }.get(result['status'], '[?]')

        if result['status'] in ('updated', 'would_update'):
            print(f"{i+1:3}/{len(raw_ids)} {status_marker} {result.get('title', 'N/A')[:50]}")
            print(f"         {result.get('old')} -> {result.get('new')}")
        elif result['status'] == 'error':
            print(f"{i+1:3}/{len(raw_ids)} {status_marker} raw_job_id={raw_id}: {result.get('message')}")

    print(f'\n=== Summary ===')
    print(f"Updated: {stats.get('updated', 0)}")
    print(f"Would update: {stats.get('would_update', 0)}")
    print(f"Unchanged: {stats.get('unchanged', 0)}")
    print(f"Errors: {stats.get('error', 0)}")


if __name__ == '__main__':
    main()
