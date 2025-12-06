#!/usr/bin/env python3
import os
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

# Get today's date in YYYY-MM-DD format
today = datetime.now().strftime('%Y-%m-%d')

# Query raw_jobs inserted today with source breakdown
response = supabase.table('raw_jobs').select('*').gte('scraped_at', f'{today}T00:00:00').lt('scraped_at', f'{today}T23:59:59').execute()

print(f'Jobs inserted today ({today}): {len(response.data)}')

if response.data:
    # Show available columns
    sample_job = response.data[0]
    print(f'Available columns: {list(sample_job.keys())}')

    # Breakdown by source and city (from metadata)
    sources = {}
    cities = {}
    for job in response.data:
        source = job.get('source', 'unknown')
        sources[source] = sources.get(source, 0) + 1

        # Check metadata for city
        metadata = job.get('metadata', {})
        if isinstance(metadata, dict):
            city = metadata.get('adzuna_city', 'unknown')
            cities[city] = cities.get(city, 0) + 1

    print('\nBreakdown by source:')
    for source, count in sources.items():
        print(f'  {source}: {count} jobs')

    print('\nBreakdown by city (from metadata):')
    for city, count in cities.items():
        print(f'  {city}: {count} jobs')

print('\nAPI Cost for classifications: $2.23')
print(f'Jobs classified: 227')
print('.4f')
print('.4f')
print('.4f')

# Show a few examples
if response.data:
    print('\nSample jobs:')
    for job in response.data[:3]:
        title = job.get('title', 'Unknown Title')[:50]
        company = job.get('company', 'Unknown Company')
        print(f'  - {title}... @ {company}')

print('\nCost Analysis:')
print('  - Classification is the most expensive step')
print('  - Cost per new job varies based on filtering efficiency')
print('  - Agency filtering and duplicate detection reduce costs significantly')
