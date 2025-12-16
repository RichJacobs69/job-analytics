#!/usr/bin/env python3
"""
Analyze jobs with blank or minimal text content
"""
import json
from collections import defaultdict

def analyze_blank_text():
    with open('recent_jobs_analysis.json', 'r') as f:
        data = json.load(f)

    print('=== ANALYSIS OF BLANK/MINIMAL TEXT JOBS ===')

    # Analyze all jobs for blank/empty text
    blank_jobs = []
    minimal_jobs = []
    normal_jobs = []

    for job in data:
        raw_text = job.get('raw_text', '').strip()
        text_length = len(raw_text)

        if text_length == 0:
            blank_jobs.append(job)
        elif text_length < 50:
            minimal_jobs.append(job)
        else:
            normal_jobs.append(job)

    print(f'Total jobs analyzed: {len(data)}')
    print(f'Blank text (0 chars): {len(blank_jobs)}')
    print(f'Minimal text (<50 chars): {len(minimal_jobs)}')
    print(f'Normal text (50+ chars): {len(normal_jobs)}')
    print()

    # Analyze blank jobs by source
    blank_by_source = defaultdict(int)
    for job in blank_jobs:
        source = job.get('source', 'unknown')
        blank_by_source[source] += 1

    print('Blank jobs by source:')
    for source, count in sorted(blank_by_source.items(), key=lambda x: x[1], reverse=True):
        print(f'  {source}: {count} jobs')

    print()

    # Analyze blank jobs by company
    blank_by_company = defaultdict(int)
    for job in blank_jobs:
        company = job.get('company', 'Unknown')
        blank_by_company[company] += 1

    print('Blank jobs by company (top 10):')
    for company, count in sorted(blank_by_company.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f'  {company}: {count} jobs')

    print()

    # Show some examples of blank jobs
    if blank_jobs:
        print('Examples of blank jobs:')
        for i, job in enumerate(blank_jobs[:5]):
            print(f'  {i+1}. {job.get("company", "Unknown")} - {job.get("title", "Unknown")}')
            print(f'     URL: {job.get("posting_url", "")}')
            print(f'     Source: {job.get("source", "unknown")}')
            print()

    # Analyze minimal jobs too
    if minimal_jobs:
        print(f'Examples of minimal text jobs (<50 chars):')
        for i, job in enumerate(minimal_jobs[:5]):
            raw_text = job.get('raw_text', '').strip()
            print(f'  {i+1}. {job.get("company", "Unknown")} - {job.get("title", "Unknown")}')
            print(f'     Length: {len(raw_text)} chars')
            print(f'     Content: "{raw_text}"')
            print(f'     URL: {job.get("posting_url", "")}')
            print(f'     Source: {job.get("source", "unknown")}')
            print()

if __name__ == "__main__":
    analyze_blank_text()




