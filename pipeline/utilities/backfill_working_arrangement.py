"""
Backfill Working Arrangement for Adzuna and Greenhouse Jobs

PURPOSE:
Reprocess jobs with working_arrangement='onsite' (the default assumption)
to classify them into: remote, hybrid, onsite (confirmed), or unknown.

The issue: Adzuna provides truncated job descriptions, so working arrangement
info is often cut off. We defaulted to 'onsite' but this is inaccurate for many jobs.
Greenhouse jobs may also benefit from re-classification based on regex patterns.

CLASSIFICATION LOGIC:
- Jobs with explicit "(Remote)" in title -> remote
- Jobs with explicit "(Hybrid)" in title -> hybrid  
- Jobs with onsite confirmation signals -> onsite (keep)
- Jobs with no determinable signal -> unknown

This script excludes false positives like "remote capture" (banking tech),
"hybrid cloud" (infrastructure), etc.

USAGE:
  python -m pipeline.utilities.backfill_working_arrangement --dry-run           # Preview all sources
  python -m pipeline.utilities.backfill_working_arrangement --source adzuna     # Adzuna only
  python -m pipeline.utilities.backfill_working_arrangement --source greenhouse # Greenhouse only
  python -m pipeline.utilities.backfill_working_arrangement --source all        # Both sources
"""

import sys
import re
import time
sys.path.insert(0, '.')

from pipeline.db_connection import supabase


def classify_working_arrangement(title: str, raw_text: str) -> str:
    """
    Classify working arrangement based on title and raw_text.
    
    Returns: 'remote', 'hybrid', 'onsite', or 'unknown'
    """
    combined = (title or '') + ' ' + (raw_text or '')
    
    # REMOTE signals (high confidence)
    remote_patterns = [
        r'\(remote\)',           # (Remote) in title
        r'remote-first',         # Remote-first
        r'fully remote',         # Fully remote
        r'100% remote',          # 100% remote
        r'remote position',      # Remote position
        r'\bwork from home\b',   # Work from home
        r'\bWFH\b',              # WFH
        r'work remotely',        # Work remotely
        r'remote work environment',  # Remote work environment
    ]
    
    # HYBRID signals (high confidence)
    hybrid_patterns = [
        r'\(hybrid\)',           # (Hybrid) in title
        r'hybrid working',       # Hybrid working
        r'hybrid model',         # Hybrid model
        r'hybrid role',          # Hybrid role
        r'\d+\s*days?.{0,10}(in\s*)?office',  # X days in office
        r'office\s*\d+\s*days?',  # Office X days
    ]
    
    # ONSITE signals (confirms onsite classification)
    onsite_patterns = [
        r'\(onsite\)',           # (Onsite) in title
        r'\(on-site\)',          # (On-site) in title
        r'office-based',         # Office-based
        r'office based',         # Office based
        r'role type:.*onsite',   # Role Type: Onsite
        r'position type:.*onsite', # Position Type: Onsite
        r'location:.*\(onsite\)', # Location: X (Onsite)
        r'on-?site\s*(role|position|work)', # Onsite role/position
        r'must be.{0,20}on-?site', # Must be onsite
    ]
    
    # False positive patterns to exclude
    false_positive_remote = [
        r'remote capture',       # Banking tech term
        r'remotely piloted',     # Drones
        r'remote onboarding',    # Identity verification
        r'remote areas',         # Geography
        r'remote communities',   # Geography
        r'remote locations',     # Geography
        r'remote regions',       # Geography
        r'remote sensing',       # Technology
        r'remote monitoring',    # Technology
    ]
    
    false_positive_hybrid = [
        r'hybrid cloud',         # Infrastructure
        r'on-prem.*hybrid',      # Infrastructure
        r'hybrid.*environment',  # Infrastructure (cloud)
        r'hybrid.*infrastructure', # Infrastructure
        r'hybrid.*solution',     # Tech solution
    ]
    
    # Check remote (exclude false positives)
    for pattern in remote_patterns:
        if re.search(pattern, combined, re.I):
            # Check for false positives
            is_false_positive = any(re.search(fp, combined, re.I) for fp in false_positive_remote)
            if not is_false_positive:
                return 'remote'
    
    # Check hybrid (exclude false positives)
    for pattern in hybrid_patterns:
        if re.search(pattern, combined, re.I):
            # Check for false positives
            is_false_positive = any(re.search(fp, combined, re.I) for fp in false_positive_hybrid)
            if not is_false_positive:
                return 'hybrid'
    
    # Check onsite confirmation
    for pattern in onsite_patterns:
        if re.search(pattern, combined, re.I):
            return 'onsite'
    
    return 'unknown'


def backfill_working_arrangement(batch_size: int = 100, dry_run: bool = False, data_source: str = "all"):
    """
    Backfill working_arrangement for jobs currently marked as 'onsite'.
    
    Args:
        batch_size: How many jobs to process before pausing
        dry_run: If True, just show what would be updated without actually updating
        data_source: Which source to process - 'adzuna', 'greenhouse', or 'all'
    """
    print("=" * 70)
    print("WORKING ARRANGEMENT BACKFILL")
    print("=" * 70)
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE'}")
    print(f"Source: {data_source.upper()}")
    print()
    
    # Step 1: Fetch jobs with working_arrangement='onsite'
    source_label = data_source if data_source != "all" else "all sources"
    print(f"[DATA] Fetching {source_label} jobs with working_arrangement='onsite'...")
    
    try:
        jobs = []
        page_size = 1000
        offset = 0
        
        while True:
            query = supabase.table("enriched_jobs") \
                .select("id, raw_job_id, title_display, working_arrangement, data_source") \
                .eq("working_arrangement", "onsite")
            
            # Filter by data source if not 'all'
            if data_source == "adzuna":
                query = query.eq("data_source", "adzuna")
            elif data_source == "greenhouse":
                query = query.eq("data_source", "greenhouse")
            # else: 'all' - no filter on data_source
            
            result = query.range(offset, offset + page_size - 1).execute()
            
            if not result.data:
                break
            
            jobs.extend(result.data)
            print(f"   [PAGE] Fetched {len(result.data)} jobs (total: {len(jobs)})")
            
            if len(result.data) < page_size:
                break
            offset += page_size
        
        total_jobs = len(jobs)
        print(f"[OK] Found {total_jobs} jobs with working_arrangement='onsite' ({source_label})")
        
        if total_jobs == 0:
            print("\n[DONE] No jobs to process!")
            return
        
    except Exception as e:
        print(f"[ERROR] Error fetching jobs: {e}")
        return
    
    # Step 2: Fetch raw job text for classification
    print("\n[DATA] Fetching raw job text...")
    
    raw_job_ids = [job['raw_job_id'] for job in jobs]
    raw_text_map = {}
    
    try:
        batch_size_raw = 500
        for i in range(0, len(raw_job_ids), batch_size_raw):
            batch_ids = raw_job_ids[i:i + batch_size_raw]
            raw_result = supabase.table("raw_jobs") \
                .select("id, raw_text") \
                .in_("id", batch_ids) \
                .execute()
            
            for row in raw_result.data:
                raw_text_map[row['id']] = row['raw_text']
            
            if len(raw_job_ids) > batch_size_raw:
                print(f"   [PAGE] Fetched raw text batch {i // batch_size_raw + 1}")
        
        print(f"[OK] Retrieved raw text for {len(raw_text_map)} jobs")
    except Exception as e:
        print(f"[WARNING] Could not fetch raw text: {e}")
        print("   Will proceed with title only (less accurate)")
        raw_text_map = {}
    
    # Step 3: Classify and update jobs
    print(f"\n[PROCESS] Classifying {total_jobs} jobs...")
    
    # Track counts
    counts = {'remote': 0, 'hybrid': 0, 'onsite': 0, 'unknown': 0}
    updates = {'remote': [], 'hybrid': [], 'unknown': []}
    error_count = 0
    
    for i, job in enumerate(jobs, 1):
        job_id = job['id']
        raw_job_id = job['raw_job_id']
        title = job['title_display']
        raw_text = raw_text_map.get(raw_job_id, '')
        
        try:
            new_arrangement = classify_working_arrangement(title, raw_text)
            counts[new_arrangement] += 1
            
            # Only update if classification changed
            if new_arrangement != 'onsite':
                updates[new_arrangement].append({
                    'id': job_id,
                    'raw_job_id': raw_job_id,
                    'title': title[:60]
                })
                
                # Print significant changes
                if new_arrangement in ('remote', 'hybrid'):
                    print(f"   [{new_arrangement.upper()}] raw_job_id={raw_job_id}: {title[:50]}...")
            
            # Progress indicator
            if i % 500 == 0:
                print(f"   [PROGRESS] Processed {i}/{total_jobs} jobs...")
        
        except Exception as e:
            print(f"   [ERROR] Error classifying job {job_id}: {e}")
            error_count += 1
    
    # Step 4: Summary before update
    print()
    print("=" * 70)
    print("CLASSIFICATION SUMMARY")
    print("=" * 70)
    print(f"Total jobs analyzed: {total_jobs}")
    print()
    print(f"  REMOTE (will update):    {counts['remote']:>5} ({counts['remote']/total_jobs*100:.2f}%)")
    print(f"  HYBRID (will update):    {counts['hybrid']:>5} ({counts['hybrid']/total_jobs*100:.2f}%)")
    print(f"  ONSITE (keep as-is):     {counts['onsite']:>5} ({counts['onsite']/total_jobs*100:.2f}%)")
    print(f"  UNKNOWN (will update):   {counts['unknown']:>5} ({counts['unknown']/total_jobs*100:.2f}%)")
    print()
    
    if counts['remote'] > 0:
        print("Jobs to update to REMOTE:")
        for u in updates['remote']:
            print(f"   raw_job_id={u['raw_job_id']}: {u['title']}")
        print()
    
    if counts['hybrid'] > 0:
        print("Jobs to update to HYBRID:")
        for u in updates['hybrid']:
            print(f"   raw_job_id={u['raw_job_id']}: {u['title']}")
        print()
    
    # Step 5: Apply updates
    if dry_run:
        print("[DRY RUN] No changes made. Run without --dry-run to apply updates.")
        return
    
    print("[UPDATE] Applying updates to database...")
    
    update_count = 0
    
    # Update remote jobs
    for u in updates['remote']:
        try:
            supabase.table("enriched_jobs") \
                .update({"working_arrangement": "remote"}) \
                .eq("id", u['id']) \
                .execute()
            update_count += 1
        except Exception as e:
            print(f"   [ERROR] Failed to update {u['id']}: {e}")
            error_count += 1
    
    # Update hybrid jobs
    for u in updates['hybrid']:
        try:
            supabase.table("enriched_jobs") \
                .update({"working_arrangement": "hybrid"}) \
                .eq("id", u['id']) \
                .execute()
            update_count += 1
        except Exception as e:
            print(f"   [ERROR] Failed to update {u['id']}: {e}")
            error_count += 1
    
    # Update unknown jobs in batches
    print(f"\n[UPDATE] Updating {len(updates['unknown'])} jobs to 'unknown'...")
    
    for i in range(0, len(updates['unknown']), batch_size):
        batch = updates['unknown'][i:i + batch_size]
        batch_ids = [u['id'] for u in batch]
        
        try:
            supabase.table("enriched_jobs") \
                .update({"working_arrangement": "unknown"}) \
                .in_("id", batch_ids) \
                .execute()
            update_count += len(batch)
            print(f"   [BATCH] Updated {i + len(batch)}/{len(updates['unknown'])} unknown jobs")
            
            # Rate limiting
            if i + batch_size < len(updates['unknown']):
                time.sleep(0.3)
        
        except Exception as e:
            print(f"   [ERROR] Failed to update batch: {e}")
            error_count += len(batch)
    
    print()
    print("=" * 70)
    print("BACKFILL COMPLETE")
    print("=" * 70)
    print(f"Successfully updated: {update_count} jobs")
    print(f"Errors: {error_count}")


def verify_backfill(data_source: str = "all"):
    """
    Verify the results of the backfill.
    
    Args:
        data_source: Which source to verify - 'adzuna', 'greenhouse', or 'all'
    """
    print()
    print("=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    source_label = data_source if data_source != "all" else "all sources"
    
    try:
        # Count jobs by working_arrangement (with pagination)
        jobs = []
        page_size = 1000
        offset = 0
        
        while True:
            query = supabase.table("enriched_jobs") \
                .select("working_arrangement, data_source")
            
            # Filter by data source if not 'all'
            if data_source == "adzuna":
                query = query.eq("data_source", "adzuna")
            elif data_source == "greenhouse":
                query = query.eq("data_source", "greenhouse")
            
            result = query.range(offset, offset + page_size - 1).execute()
            
            if not result.data:
                break
            jobs.extend(result.data)
            if len(result.data) < page_size:
                break
            offset += page_size
        
        total = len(jobs)
        
        # Count by arrangement
        counts = {}
        for job in jobs:
            arr = job['working_arrangement']
            counts[arr] = counts.get(arr, 0) + 1
        
        # Also count by source if showing all
        source_counts = {}
        for job in jobs:
            src = job['data_source']
            source_counts[src] = source_counts.get(src, 0) + 1
        
        print(f"\nJobs by working_arrangement ({source_label}):")
        print(f"  Total: {total}")
        for arr, count in sorted(counts.items()):
            pct = count / total * 100 if total > 0 else 0
            print(f"  {arr:12}: {count:>5} ({pct:.1f}%)")
        
        if data_source == "all" and len(source_counts) > 1:
            print(f"\nBy data source:")
            for src, count in sorted(source_counts.items()):
                pct = count / total * 100 if total > 0 else 0
                print(f"  {src:12}: {count:>5} ({pct:.1f}%)")
        
        # Check for remaining 'onsite' jobs
        onsite_count = counts.get('onsite', 0)
        unknown_count = counts.get('unknown', 0)
        
        print()
        if onsite_count > 0:
            print(f"[INFO] {onsite_count} jobs remain as 'onsite' (confirmed by pattern)")
        if unknown_count > 0:
            print(f"[INFO] {unknown_count} jobs now marked as 'unknown' (no signal in truncated text)")
        
        print("\n[OK] Verification complete!")
    
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")


if __name__ == "__main__":
    import sys
    
    # Parse arguments
    dry_run = "--dry-run" in sys.argv or "-d" in sys.argv
    verify_only = "--verify" in sys.argv or "-v" in sys.argv
    
    # Parse --source argument
    data_source = "all"  # Default to all sources
    for i, arg in enumerate(sys.argv):
        if arg == "--source" and i + 1 < len(sys.argv):
            data_source = sys.argv[i + 1].lower()
            if data_source not in ("adzuna", "greenhouse", "all"):
                print(f"[ERROR] Invalid source '{data_source}'. Use: adzuna, greenhouse, or all")
                sys.exit(1)
            break
    
    if verify_only:
        verify_backfill(data_source=data_source)
    else:
        backfill_working_arrangement(batch_size=100, dry_run=dry_run, data_source=data_source)
        verify_backfill(data_source=data_source)
    
    print()
    print("=" * 70)
    print("USAGE:")
    print("  python -m pipeline.utilities.backfill_working_arrangement --dry-run              # Preview all")
    print("  python -m pipeline.utilities.backfill_working_arrangement --source adzuna        # Adzuna only")
    print("  python -m pipeline.utilities.backfill_working_arrangement --source greenhouse    # Greenhouse only")
    print("  python -m pipeline.utilities.backfill_working_arrangement --source all           # Both sources")
    print("  python -m pipeline.utilities.backfill_working_arrangement --verify               # Verify only")
    print("=" * 70)

