"""
Backfill Agency Flags
Reprocess all existing jobs in enriched_jobs table to add agency detection flags.
"""

from db_connection import supabase
from agency_detection import detect_agency
import time

def backfill_agency_flags(batch_size: int = 50, dry_run: bool = False, force_reprocess: bool = False):
    """
    Reprocess jobs in enriched_jobs to add/update agency flags.
    
    Args:
        batch_size: How many jobs to process at once
        dry_run: If True, just show what would be updated without actually updating
        force_reprocess: If True, reprocess ALL jobs (even those with existing flags)
    """
    print("=" * 70)
    print("AGENCY FLAG BACKFILL")
    print("=" * 70)
    
    # Load hard filter for priority checking
    import yaml
    with open('config/agency_blacklist.yaml') as f:
        AGENCY_CONFIG = yaml.safe_load(f)
    HARD_FILTER = set(agency.lower().strip() for agency in AGENCY_CONFIG['hard_filter'])
    print(f"[PROTECT] Loaded hard filter: {len(HARD_FILTER)} agencies")
    
    # Step 1: Get all jobs that need agency flags
    print("\n[DATA] Fetching jobs from database...")
    
    try:
        if force_reprocess:
            # Reprocess ALL jobs (useful after updating blacklist)
            result = supabase.table("enriched_jobs") \
                .select("id, raw_job_id, employer_name, is_agency, agency_confidence") \
                .execute()
            print(f"[OK] Found {len(result.data)} jobs (FORCE REPROCESS mode)")
        else:
            # Only process jobs with NULL agency flags
            result = supabase.table("enriched_jobs") \
                .select("id, raw_job_id, employer_name, is_agency, agency_confidence") \
                .is_("is_agency", "null") \
                .execute()
            print(f"[OK] Found {len(result.data)} jobs with NULL agency flags")
        
        jobs = result.data
        total_jobs = len(jobs)
        
        if total_jobs == 0:
            print("\n[DONE] All jobs already have agency flags!")
            return
        
    except Exception as e:
        print(f"[ERROR] Error fetching jobs: {e}")
        return
    
    # Step 2: Also get raw job text for better detection
    print("\n[NOTE] Fetching raw job text for enhanced detection...")
    
    # Build a map of raw_job_id -> job text
    raw_job_ids = [job['raw_job_id'] for job in jobs]
    
    try:
        raw_result = supabase.table("raw_jobs") \
            .select("id, raw_text") \
            .in_("id", raw_job_ids) \
            .execute()
        
        raw_text_map = {row['id']: row['raw_text'] for row in raw_result.data}
        print(f"[OK] Retrieved raw text for {len(raw_text_map)} jobs")
    except Exception as e:
        print(f"[WARNING] Could not fetch raw text: {e}")
        print("   Will proceed with employer name only (less accurate)")
        raw_text_map = {}
    
    # Step 3: Process jobs in batches
    print(f"\n[PROCESS] Processing {total_jobs} jobs...")
    print(f"   Dry run: {'YES (no changes will be made)' if dry_run else 'NO (will update database)'}")
    print()
    
    updated_count = 0
    agency_count = 0
    error_count = 0
    corrected_count = 0  # Jobs that were wrong and got corrected
    
    for i, job in enumerate(jobs, 1):
        employer_name = job['employer_name']
        job_id = job['id']
        raw_job_id = job['raw_job_id']
        current_is_agency = job.get('is_agency')
        
        # Get raw text if available
        job_text = raw_text_map.get(raw_job_id)
        
        try:
            # PRIORITY CHECK: Is employer in hard filter?
            # This takes precedence over any pattern matching
            employer_lower = employer_name.lower().strip() if employer_name else ""
            
            if employer_lower in HARD_FILTER:
                # Hard filter match = definitely an agency
                is_agency = True
                confidence = 'high'
                status = "[BLOCKED]"
                
                # Track if we're correcting a wrong classification
                if current_is_agency is False:
                    corrected_count += 1
                    status = "[FIX]"  # Correction icon
            else:
                # Not in hard filter, run pattern matching
                is_agency, confidence = detect_agency(employer_name, job_text)
                status = "[DETECT]" if is_agency else "[OK]"
                
                # Track corrections
                if current_is_agency is not None and current_is_agency != is_agency:
                    corrected_count += 1
                    status = "[FIX]"
            
            # Show progress with status indicator
            print(f"{status} [{i}/{total_jobs}] {employer_name[:40]:40} → is_agency={is_agency:5} ({confidence})")
            
            if is_agency:
                agency_count += 1
            
            # Update database (unless dry run)
            if not dry_run:
                supabase.table("enriched_jobs") \
                    .update({
                        "is_agency": is_agency,
                        "agency_confidence": confidence
                    }) \
                    .eq("id", job_id) \
                    .execute()
                
                updated_count += 1
                
                # Rate limiting (be nice to Supabase)
                if i % batch_size == 0:
                    print(f"   [PAUSE] Batch complete, pausing briefly...")
                    time.sleep(0.5)
        
        except Exception as e:
            print(f"   [ERROR] Error processing job {job_id}: {e}")
            error_count += 1
            continue
    
    # Step 4: Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total jobs processed: {total_jobs}")
    print(f"Agencies detected: {agency_count} ({agency_count/total_jobs*100:.1f}%)")
    print(f"Corrections made: {corrected_count} (were wrong, now fixed)")
    
    if not dry_run:
        print(f"Successfully updated: {updated_count}")
        print(f"Errors: {error_count}")
        print("\n[OK] Backfill complete!")
    else:
        print("\n[TIP] This was a dry run. Run with dry_run=False to apply changes.")
    
    # Step 5: Show sample of detected agencies
    if agency_count > 0:
        print("\n" + "=" * 70)
        print("SAMPLE OF DETECTED AGENCIES")
        print("=" * 70)
        
        try:
            sample = supabase.table("enriched_jobs") \
                .select("employer_name, agency_confidence, job_subfamily") \
                .eq("is_agency", True) \
                .order("id", desc=True) \
                .limit(10) \
                .execute()
            
            for row in sample.data:
                print(f"  • {row['employer_name']:40} ({row['agency_confidence']}) - {row['job_subfamily']}")
        
        except Exception as e:
            print(f"[WARNING] Could not fetch sample: {e}")


def verify_backfill():
    """
    Verify that backfill worked correctly.
    """
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    try:
        # Count jobs by agency status
        result = supabase.table("enriched_jobs") \
            .select("is_agency, agency_confidence") \
            .execute()
        
        jobs = result.data
        total = len(jobs)
        
        # Count by status
        null_count = sum(1 for j in jobs if j['is_agency'] is None)
        agency_count = sum(1 for j in jobs if j['is_agency'] is True)
        non_agency_count = sum(1 for j in jobs if j['is_agency'] is False)
        
        print(f"\nTotal jobs in database: {total}")
        print(f"  [OK] Direct employers: {non_agency_count} ({non_agency_count/total*100:.1f}%)")
        print(f"  [DETECT] Agencies: {agency_count} ({agency_count/total*100:.1f}%)")
        print(f"  ❓ NULL (not processed): {null_count} ({null_count/total*100:.1f}%)")
        
        if null_count == 0:
            print("\n[DONE] All jobs have been processed!")
        else:
            print(f"\n[WARNING] {null_count} jobs still need processing")
        
        # Count by confidence
        if agency_count > 0:
            print("\nAgency confidence breakdown:")
            high = sum(1 for j in jobs if j['is_agency'] is True and j['agency_confidence'] == 'high')
            medium = sum(1 for j in jobs if j['is_agency'] is True and j['agency_confidence'] == 'medium')
            low = sum(1 for j in jobs if j['is_agency'] is True and j['agency_confidence'] == 'low')
            
            print(f"  High confidence: {high} ({high/agency_count*100:.1f}%)")
            print(f"  Medium confidence: {medium} ({medium/agency_count*100:.1f}%)")
            print(f"  Low confidence: {low} ({low/agency_count*100:.1f}%)")
    
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")


if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    dry_run = "--dry-run" in sys.argv or "-d" in sys.argv
    verify_only = "--verify" in sys.argv or "-v" in sys.argv
    force_reprocess = "--force" in sys.argv or "-f" in sys.argv
    
    if verify_only:
        verify_backfill()
    else:
        # Run backfill
        backfill_agency_flags(batch_size=50, dry_run=dry_run, force_reprocess=force_reprocess)
        
        # Then verify
        verify_backfill()
        
    print("\n" + "=" * 70)
    print("USAGE:")
    print("  python backfill_agency_flags.py              # Process jobs with NULL flags")
    print("  python backfill_agency_flags.py --force      # Reprocess ALL jobs (after blacklist update)")
    print("  python backfill_agency_flags.py --dry-run    # Preview without updating")
    print("  python backfill_agency_flags.py --verify     # Just check current state")
    print("=" * 70)