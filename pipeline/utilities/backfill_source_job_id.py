"""
Backfill source_job_id for raw_jobs records where it is NULL.

Extracts job IDs from posting_url patterns:
- Greenhouse/Stripe: /jobs/listing/{slug}/7306915 -> 7306915
- Adzuna: /ad/5508693775 -> 5508693775  
- Manual/LinkedIn: Uses URL hash as stable identifier

Usage:
    python pipeline/utilities/backfill_source_job_id.py --dry-run  # Preview changes
    python pipeline/utilities/backfill_source_job_id.py --live     # Apply changes
"""

import sys
import re
import hashlib
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.db_connection import supabase


def extract_job_id_from_url(url: str, source: str) -> str | None:
    """
    Extract job ID from posting URL based on source type.
    
    Args:
        url: The posting URL
        source: The data source (greenhouse, adzuna, manual)
        
    Returns:
        Extracted job ID or None if extraction fails
    """
    if not url:
        return None
    
    if source == 'greenhouse':
        # Greenhouse URLs: /jobs/listing/{slug}/7306915 or /jobs/7306915
        # Look for 6+ digit numeric ID at end of path
        match = re.search(r'/(\d{6,})(?:\?|$)', url)
        if match:
            return match.group(1)
        # Fallback: standard /jobs/ID
        match = re.search(r'/jobs/(\d+)', url)
        if match:
            return match.group(1)
            
    elif source == 'adzuna':
        # Adzuna URLs: /ad/5508693775?...
        match = re.search(r'/ad/(\d+)', url)
        if match:
            return match.group(1)
            
    elif source == 'manual':
        # Manual entries don't have a structured ID
        # Use a hash of the URL as a stable identifier
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"manual_{url_hash}"
    
    # Generic fallback: look for any 6+ digit number in URL
    match = re.search(r'/(\d{6,})', url)
    if match:
        return match.group(1)
    
    return None


def fetch_null_source_job_ids():
    """Fetch all raw_jobs records with NULL source_job_id."""
    print("Fetching records with NULL source_job_id...")
    
    all_records = []
    offset = 0
    batch_size = 1000
    
    while True:
        result = supabase.table('raw_jobs') \
            .select('id, source, posting_url, title') \
            .is_('source_job_id', 'null') \
            .range(offset, offset + batch_size - 1) \
            .execute()
        
        if not result.data:
            break
            
        all_records.extend(result.data)
        print(f"  Fetched {len(all_records)} records...")
        offset += batch_size
        
        if len(result.data) < batch_size:
            break
    
    return all_records


def backfill_source_job_ids(dry_run: bool = True):
    """
    Backfill source_job_id for records where it is NULL.
    
    Args:
        dry_run: If True, only preview changes without updating DB
    """
    records = fetch_null_source_job_ids()
    
    if not records:
        print("\nNo records found with NULL source_job_id!")
        return
    
    print(f"\nFound {len(records)} records with NULL source_job_id")
    print("="*80)
    
    # Group by source for reporting
    by_source = {}
    for r in records:
        source = r.get('source', 'unknown')
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(r)
    
    print("\nBreakdown by source:")
    for source, source_records in by_source.items():
        print(f"  {source}: {len(source_records)} records")
    
    print("\n" + "="*80)
    mode = "DRY RUN (preview only)" if dry_run else "LIVE (updating database)"
    print(f"Mode: {mode}")
    print("="*80 + "\n")
    
    # Process each record
    success_count = 0
    fail_count = 0
    
    for i, record in enumerate(records, 1):
        record_id = record['id']
        source = record.get('source', 'unknown')
        url = record.get('posting_url', '')
        title = record.get('title', 'Unknown')[:50]
        
        # Extract job ID from URL
        extracted_id = extract_job_id_from_url(url, source)
        
        if extracted_id:
            print(f"[{i}/{len(records)}] {source}: {title}...")
            print(f"    URL: {url[:80]}...")
            print(f"    Extracted ID: {extracted_id}")
            
            if not dry_run:
                try:
                    supabase.table('raw_jobs').update({
                        'source_job_id': extracted_id
                    }).eq('id', record_id).execute()
                    print(f"    ✓ Updated")
                except Exception as e:
                    print(f"    ✗ Failed: {str(e)[:100]}")
                    fail_count += 1
                    continue
            
            success_count += 1
        else:
            print(f"[{i}/{len(records)}] {source}: {title}...")
            print(f"    URL: {url[:80]}...")
            print(f"    ✗ Could not extract ID")
            fail_count += 1
    
    # Summary
    print("\n" + "="*80)
    print("BACKFILL SUMMARY")
    print("="*80)
    print(f"Total records processed: {len(records)}")
    print(f"IDs extracted: {success_count}")
    print(f"Failed to extract: {fail_count}")
    
    if dry_run:
        print(f"\nThis was a DRY RUN. Run with --live to apply changes.")
    else:
        print(f"\nDatabase updated with {success_count} new source_job_ids")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill source_job_id from posting URLs')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without updating')
    parser.add_argument('--live', action='store_true', help='Apply changes to database')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.live:
        print("Please specify --dry-run or --live")
        print("Example: python backfill_source_job_id.py --dry-run")
        sys.exit(1)
    
    dry_run = not args.live
    backfill_source_job_ids(dry_run=dry_run)


if __name__ == '__main__':
    main()

