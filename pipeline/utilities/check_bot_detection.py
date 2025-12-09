#!/usr/bin/env python3
"""
Check how many jobs in raw_jobs have bot detection/challenge page text
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.db_connection import supabase

# Bot detection indicators
BOT_INDICATORS = [
    "Enable JavaScript and cookies to continue",
    "challenge-error",
    "Verify you are human",
    "cloudflare",
    "security check"
]

def check_bot_detection():
    """Check raw_jobs table for bot detection text"""

    print("Fetching all Greenhouse raw jobs...")

    # Paginate through all Greenhouse jobs
    all_jobs = []
    offset = 0
    page_size = 1000

    while True:
        result = supabase.table('raw_jobs') \
            .select('id,company,raw_text,metadata') \
            .eq('source', 'greenhouse') \
            .offset(offset) \
            .limit(page_size) \
            .execute()

        if not result.data:
            break

        all_jobs.extend(result.data)
        offset += page_size

        if len(result.data) < page_size:
            break

    print(f"Found {len(all_jobs)} Greenhouse jobs\n")

    # Check each job for bot detection
    affected_jobs = []
    by_company = {}

    for job in all_jobs:
        raw_text = job.get('raw_text', '')
        company = job.get('company', 'Unknown')

        # More specific check: bot detection is typically short text with challenge keywords
        # Real job postings are usually 1000+ chars
        is_short = len(raw_text) < 500
        has_challenge = 'challenge-error' in raw_text.lower() or 'verify you are human' in raw_text.lower()
        has_js_warning = 'enable javascript and cookies' in raw_text.lower()

        is_bot_detection = is_short and (has_challenge or has_js_warning)

        if is_bot_detection:
            affected_jobs.append(job)
            if company not in by_company:
                by_company[company] = 0
            by_company[company] += 1

    # Results
    print(f"Bot detection found in: {len(affected_jobs)} jobs ({len(affected_jobs)/len(all_jobs)*100:.1f}%)\n")

    if affected_jobs:
        print("Affected companies:")
        for company, count in sorted(by_company.items(), key=lambda x: x[1], reverse=True):
            print(f"  {company}: {count} jobs")

        # Show example
        print(f"\nExample affected job (first 300 chars):")
        example = affected_jobs[0]
        print(f"Company: {example['company']}")
        print(f"Raw text: {example['raw_text'][:300]}...")
    else:
        print("No bot detection found!")

if __name__ == '__main__':
    check_bot_detection()
