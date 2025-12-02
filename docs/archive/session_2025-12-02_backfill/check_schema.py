"""Quick script to check the schema of raw_jobs and enriched_jobs tables."""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Get one row from raw_jobs to see columns
print("RAW_JOBS COLUMNS:")
raw_sample = supabase.table("raw_jobs").select("*").limit(1).execute()
if raw_sample.data:
    print(list(raw_sample.data[0].keys()))

print("\nENRICHED_JOBS COLUMNS:")
enriched_sample = supabase.table("enriched_jobs").select("*").limit(1).execute()
if enriched_sample.data:
    print(list(enriched_sample.data[0].keys()))
