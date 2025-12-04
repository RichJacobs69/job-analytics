"""
Check for orphan enriched_jobs (raw_job_id points to deleted raw_jobs)
"""

import sys
sys.path.insert(0, '.')
from pipeline.db_connection import supabase

print("Checking for orphan enriched_jobs...")

# Get counts
enriched_count = supabase.table('enriched_jobs').select('*', count='exact').execute()
raw_count = supabase.table('raw_jobs').select('*', count='exact').execute()

print(f"Total enriched_jobs in DB: {enriched_count.count}")
print(f"Total raw_jobs in DB: {raw_count.count}")

# Get ALL enriched job raw_job_ids (paginate)
print("Fetching all enriched_jobs...")
all_enriched = []
offset = 0
while True:
    batch = supabase.table('enriched_jobs').select('id, raw_job_id, title_display').range(offset, offset + 999).execute()
    if not batch.data:
        break
    all_enriched.extend(batch.data)
    offset += 1000
print(f"  Total fetched: {len(all_enriched)}")

# Get ALL raw job ids (paginate)  
print("Fetching all raw_jobs...")
all_raw_ids = set()
offset = 0
while True:
    batch = supabase.table('raw_jobs').select('id').range(offset, offset + 999).execute()
    if not batch.data:
        break
    all_raw_ids.update(job['id'] for job in batch.data)
    offset += 1000
print(f"  Total fetched: {len(all_raw_ids)}")

# Find orphans
orphans = [job for job in all_enriched if job['raw_job_id'] not in all_raw_ids]
print(f"\nOrphan enriched_jobs: {len(orphans)}")

if orphans:
    print("\nSample orphans:")
    for job in orphans[:10]:
        title = job['title_display'][:50] if job['title_display'] else 'N/A'
        raw_id = job['raw_job_id']
        print(f"  enriched_id={job['id']}, raw_job_id={raw_id}, title={title}")
    
    print(f"\nOrphan raw_job_ids: {[o['raw_job_id'] for o in orphans[:20]]}")
else:
    print("\n✅ No orphans found!")

