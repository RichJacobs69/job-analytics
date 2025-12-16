#!/usr/bin/env python3
"""
Check for blank jobs over a longer historical period
"""
from pipeline.db_connection import supabase
from datetime import datetime, timedelta

def check_blank_historical():
    # Check for blank jobs in a broader time range
    print('Checking for blank jobs across a longer time period...')

    # Query for jobs with very short text from the last 30 days
    query = supabase.table('raw_jobs').select('''
        id, source, posting_url, title, company, raw_text, scraped_at
    ''').gte('scraped_at', (datetime.now() - timedelta(days=30)).isoformat()).limit(2000)

    result = query.execute()

    blank_jobs = []
    very_short_jobs = []

    for job in result.data:
        raw_text = job.get('raw_text', '').strip()
        length = len(raw_text)

        if length == 0:
            blank_jobs.append(job)
        elif length < 20:
            very_short_jobs.append(job)

    print(f'\n=== BLANK TEXT ANALYSIS (Last 30 days, {len(result.data)} jobs) ===')
    print(f'Completely blank (0 chars): {len(blank_jobs)}')
    print(f'Very short (<20 chars): {len(very_short_jobs)}')

    if blank_jobs:
        print(f'\n=== COMPLETELY BLANK JOBS ===')
        for job in blank_jobs[:5]:
            print(f'- {job.get("company", "Unknown")}: {job.get("title", "Unknown")} ({job.get("source", "unknown")})')
            print(f'  Scraped: {job.get("scraped_at", "unknown")}')

    if very_short_jobs:
        print(f'\n=== VERY SHORT JOBS (<20 chars) ===')
        for job in very_short_jobs[:5]:
            raw_text = job.get('raw_text', '')
            print(f'- {job.get("company", "Unknown")}: "{raw_text}" ({len(raw_text)} chars, {job.get("source", "unknown")})')

if __name__ == "__main__":
    check_blank_historical()




