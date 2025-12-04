"""
Backfill Script: Re-classify out_of_scope jobs using improved classifier

Usage:
------
# Dry run (no database changes):
python pipeline/utilities/backfill_out_of_scope.py --dry-run --limit 10

# Full run with database updates:
python pipeline/utilities/backfill_out_of_scope.py --live
"""

import os
import sys
import argparse
import time
from datetime import datetime

sys.path.insert(0, '.')
from dotenv import load_dotenv
from supabase import create_client
from pipeline.classifier import classify_job_with_claude

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))


def get_out_of_scope_jobs(limit: int = None):
    """Get all jobs currently classified as out_of_scope."""
    print("Fetching out_of_scope jobs...")
    
    query = supabase.table('enriched_jobs').select(
        'id, raw_job_id, employer_name, title_display, job_family, job_subfamily, '
        'seniority, city_code, working_arrangement, data_source'
    ).eq('job_family', 'out_of_scope').eq('is_agency', False)
    
    if limit:
        query = query.limit(limit)
    else:
        query = query.limit(2000)
    
    enriched_result = query.execute()
    
    if not enriched_result.data:
        return []
    
    print(f"Found {len(enriched_result.data)} out_of_scope jobs")
    
    # Get raw_job_ids
    raw_job_ids = [job['raw_job_id'] for job in enriched_result.data]
    
    # Fetch raw_jobs
    print("Fetching raw job data...")
    raw_jobs_data = {}
    batch_size = 100
    
    for i in range(0, len(raw_job_ids), batch_size):
        batch_ids = raw_job_ids[i:i+batch_size]
        raw_result = supabase.table('raw_jobs').select(
            'id, title, company, raw_text, source'
        ).in_('id', batch_ids).execute()
        
        for raw in raw_result.data:
            raw_jobs_data[raw['id']] = raw
    
    # Combine enriched + raw data
    jobs_to_process = []
    for enriched in enriched_result.data:
        raw_job_id = enriched['raw_job_id']
        if raw_job_id in raw_jobs_data:
            raw = raw_jobs_data[raw_job_id]
            jobs_to_process.append({
                'enriched_id': enriched['id'],
                'raw_job_id': raw_job_id,
                'title': raw.get('title') or enriched.get('title_display') or 'Unknown',
                'company': raw.get('company') or enriched.get('employer_name') or 'Unknown',
                'raw_text': raw.get('raw_text', ''),
                'source': raw.get('source', 'unknown'),
                'current_family': enriched['job_family'],
                'city_code': enriched.get('city_code', 'unk'),
            })
    
    print(f"Prepared {len(jobs_to_process)} jobs for re-classification")
    return jobs_to_process


def reclassify_job(job: dict):
    """Re-classify a single job using the improved classifier."""
    structured_input = {
        'title': job['title'],
        'company': job['company'],
        'description': job['raw_text'],
        'location': job.get('city_code', 'unk'),
        'category': 'IT Jobs',
    }
    
    return classify_job_with_claude(
        job_text=job['raw_text'],
        structured_input=structured_input,
        verbose=False
    )


def update_enriched_job(enriched_id: int, classification: dict):
    """Update an enriched_job record with new classification."""
    role = classification.get('role', {})
    
    update_data = {
        'job_family': role.get('job_family') or 'out_of_scope',
        'job_subfamily': role.get('job_subfamily'),
        'seniority': role.get('seniority'),
        'track': role.get('track'),
    }
    
    update_data = {k: v for k, v in update_data.items() if v is not None}
    
    supabase.table('enriched_jobs').update(update_data).eq('id', enriched_id).execute()


def run_backfill(dry_run: bool = True, limit: int = None):
    """Main backfill function."""
    start_time = time.time()
    
    print("="*80)
    print("BACKFILL: Re-classify out_of_scope jobs")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE (will update DB)'}")
    print("="*80)
    
    jobs = get_out_of_scope_jobs(limit=limit)
    
    if not jobs:
        print("\nNo jobs to process.")
        return
    
    stats = {
        'total': len(jobs),
        'processed': 0,
        'to_product': 0,
        'to_data': 0,
        'still_out_of_scope': 0,
        'errors': 0,
        'cost': 0.0,
    }
    
    subfamily_counts = {'product': {}, 'data': {}}
    
    print(f"\nProcessing {stats['total']} jobs...\n")
    
    for i, job in enumerate(jobs, 1):
        try:
            classification = reclassify_job(job)
            stats['processed'] += 1
            
            if '_cost_data' in classification:
                stats['cost'] += classification['_cost_data'].get('total_cost', 0)
            
            new_family = classification.get('role', {}).get('job_family', 'out_of_scope')
            new_subfamily = classification.get('role', {}).get('job_subfamily')
            
            if new_family == 'product':
                stats['to_product'] += 1
                subfamily_counts['product'][new_subfamily] = subfamily_counts['product'].get(new_subfamily, 0) + 1
                symbol = "→ PRODUCT"
            elif new_family == 'data':
                stats['to_data'] += 1
                subfamily_counts['data'][new_subfamily] = subfamily_counts['data'].get(new_subfamily, 0) + 1
                symbol = "→ DATA"
            else:
                stats['still_out_of_scope'] += 1
                symbol = "= out_of_scope"
            
            title_short = job['title'][:45] if job['title'] else 'Unknown'
            print(f"[{i}/{stats['total']}] {title_short}... {symbol}")
            
            # Update DB if live mode and reclassified
            if not dry_run and new_family != 'out_of_scope':
                update_enriched_job(job['enriched_id'], classification)
            
        except Exception as e:
            stats['errors'] += 1
            print(f"[{i}/{stats['total']}] ERROR: {str(e)[:60]}")
    
    # Report
    elapsed = time.time() - start_time
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"Processed: {stats['processed']}/{stats['total']} | Errors: {stats['errors']}")
    print(f"Time: {elapsed:.1f}s | Cost: ${stats['cost']:.4f}")
    print(f"\n→ PRODUCT: {stats['to_product']} ({stats['to_product']/max(stats['processed'],1)*100:.1f}%)")
    print(f"→ DATA: {stats['to_data']} ({stats['to_data']/max(stats['processed'],1)*100:.1f}%)")
    print(f"= OUT_OF_SCOPE: {stats['still_out_of_scope']} ({stats['still_out_of_scope']/max(stats['processed'],1)*100:.1f}%)")
    
    if subfamily_counts['product']:
        print("\nProduct subfamilies:")
        for sf, cnt in sorted(subfamily_counts['product'].items(), key=lambda x: -x[1]):
            print(f"  {sf or 'None'}: {cnt}")
    
    if subfamily_counts['data']:
        print("\nData subfamilies:")
        for sf, cnt in sorted(subfamily_counts['data'].items(), key=lambda x: -x[1]):
            print(f"  {sf or 'None'}: {cnt}")
    
    if dry_run:
        print("\n⚠️  DRY RUN - No DB changes. Use --live to apply.")
    else:
        print(f"\n✅ Updated {stats['to_product'] + stats['to_data']} jobs in DB")
    
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='No DB changes')
    parser.add_argument('--live', action='store_true', help='Update database')
    parser.add_argument('--limit', type=int, default=None, help='Limit jobs')
    
    args = parser.parse_args()
    dry_run = not args.live
    
    run_backfill(dry_run=dry_run, limit=args.limit)

