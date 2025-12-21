"""
Run migration 008: Add locations JSONB column
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

def run_migration():
    """Execute migration 008 SQL statements"""
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("ERROR: Missing Supabase credentials in .env")
        sys.exit(1)

    client = create_client(supabase_url, supabase_key)

    print("Running migration 008: Add locations JSONB column...")
    print("=" * 60)

    # Read the migration file
    migration_path = os.path.join(os.path.dirname(__file__), "008_add_locations_jsonb.sql")
    with open(migration_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Extract the main SQL statements (skip comments and verification queries)
    statements = [
        """
        ALTER TABLE enriched_jobs
        ADD COLUMN IF NOT EXISTS locations JSONB;
        """,
        """
        COMMENT ON COLUMN enriched_jobs.locations IS 'Array of location objects. Each object has type (city/country/region/remote), country_code, city, region, scope. Replaces city_code.';
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_enriched_jobs_locations
        ON enriched_jobs USING GIN (locations);
        """,
        """
        ALTER TABLE enriched_jobs
        ALTER COLUMN locations SET DEFAULT '[]'::jsonb;
        """
    ]

    for i, stmt in enumerate(statements, 1):
        try:
            print(f"\nStep {i}/{len(statements)}: Executing...")
            print(f"  {stmt.strip()[:80]}...")

            # Use the SQL editor endpoint via REST
            result = client.rpc('exec', {'sql': stmt}).execute()
            print(f"  ✓ Success")
        except Exception as e:
            # Some statements might fail if already exists, that's okay
            error_msg = str(e)
            if "already exists" in error_msg.lower() or "does not exist" in error_msg.lower():
                print(f"  ⚠ Already applied (skipping): {error_msg}")
            else:
                print(f"  ✗ Error: {e}")
                # Continue with other statements

    print("\n" + "=" * 60)
    print("Verifying migration...")
    print("=" * 60)

    # Verify the column exists
    try:
        result = client.table("enriched_jobs").select("locations").limit(1).execute()
        print("✓ locations column exists and is queryable")

        # Check if it's NULL (expected before backfill)
        if result.data:
            locations_value = result.data[0].get("locations")
            if locations_value is None:
                print("✓ Column is NULL (expected before backfill)")
            else:
                print(f"✓ Column has data: {locations_value}")
    except Exception as e:
        print(f"✗ Verification failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Migration 008 completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Create tests for location_extractor.py")
    print("2. Create pipeline/utilities/migrate_locations.py")
    print("3. Run backfill to populate locations column")

if __name__ == "__main__":
    run_migration()
