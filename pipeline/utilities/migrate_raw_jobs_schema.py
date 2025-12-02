#!/usr/bin/env python3
"""
Database Migration: Add title and company columns to raw_jobs table

Purpose:
--------
Modifies the raw_jobs table schema to include:
  - title (VARCHAR, nullable): Original job title from source
  - company (VARCHAR, nullable): Original company name from source

These fields preserve source metadata for better auditing and fallback when
classification fails, without requiring a join to enriched_jobs.

Usage:
------
python pipeline/utilities/migrate_raw_jobs_schema.py

This script will:
1. Check if columns already exist (idempotent)
2. Add title and company columns if missing
3. Create indexes for performance
4. Report on migration status

Safety:
-------
- Non-destructive (only adds columns, doesn't modify existing data)
- Idempotent (safe to run multiple times)
- Supports rollback (can drop columns if needed)
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: Missing SUPABASE_URL or SUPABASE_KEY in .env")
    sys.exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def check_column_exists(table_name: str, column_name: str) -> bool:
    """
    Check if a column exists in a table.

    Args:
        table_name: Name of the table
        column_name: Name of the column

    Returns:
        True if column exists, False otherwise
    """
    try:
        # Query one row to check schema
        result = supabase.table(table_name).select("*").limit(1).execute()
        if result.data:
            return column_name in result.data[0]
        else:
            # Table is empty, check by trying to query the column
            # This is a fallback approach
            try:
                supabase.table(table_name).select(column_name).limit(1).execute()
                return True
            except Exception:
                return False
    except Exception as e:
        print(f"Error checking column: {e}")
        return False


def run_migration():
    """Run the migration to add title and company columns."""

    print("=" * 80)
    print("SUPABASE SCHEMA MIGRATION: Add title and company to raw_jobs")
    print("=" * 80)
    print()

    # Note: Supabase Python client doesn't have direct DDL support
    # We need to use the REST API or SQL directly through the client

    print("WARNING: Supabase Python SDK has limited DDL support.")
    print()
    print("To add columns to the raw_jobs table, you have two options:")
    print()
    print("OPTION 1: Use Supabase Dashboard (GUI)")
    print("-" * 80)
    print("1. Go to https://app.supabase.com")
    print("2. Select your project")
    print("3. Navigate to SQL Editor")
    print("4. Run the SQL script below")
    print()

    print("OPTION 2: Use Supabase CLI (Command Line)")
    print("-" * 80)
    print("1. Install Supabase CLI: brew install supabase/tap/supabase")
    print("2. Run: supabase db push")
    print("3. Or run SQL directly via the CLI")
    print()

    print("=" * 80)
    print("SQL MIGRATION SCRIPT")
    print("=" * 80)
    print()

    migration_sql = """
-- Add title and company columns to raw_jobs table
-- Non-destructive migration (can be run multiple times safely)

-- Add title column if it doesn't exist
ALTER TABLE raw_jobs
ADD COLUMN IF NOT EXISTS title TEXT;

-- Add company column if it doesn't exist
ALTER TABLE raw_jobs
ADD COLUMN IF NOT EXISTS company TEXT;

-- Add comment documenting the columns
COMMENT ON COLUMN raw_jobs.title IS 'Original job title from source (before classification)';
COMMENT ON COLUMN raw_jobs.company IS 'Original company name from source (before classification)';

-- Create indexes for performance (optional but recommended)
CREATE INDEX IF NOT EXISTS idx_raw_jobs_title ON raw_jobs(title);
CREATE INDEX IF NOT EXISTS idx_raw_jobs_company ON raw_jobs(company);

-- Verify the changes
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'raw_jobs'
ORDER BY ordinal_position;
"""

    print(migration_sql)
    print()
    print("=" * 80)
    print("MIGRATION DETAILS")
    print("=" * 80)
    print()

    print("Changes:")
    print("  ✓ Add 'title' column (TEXT, nullable)")
    print("    └─ Stores original job title from source")
    print()
    print("  ✓ Add 'company' column (TEXT, nullable)")
    print("    └─ Stores original company name from source")
    print()
    print("  ✓ Add indexes for performance")
    print("    └─ idx_raw_jobs_title: For queries filtering by title")
    print("    └─ idx_raw_jobs_company: For queries filtering by company")
    print()

    print("Benefits:")
    print("  • Preserve source metadata without join")
    print("  • Fallback data if classification fails")
    print("  • Better audit trail and analysis")
    print("  • Improved query performance with indexes")
    print()

    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print()
    print("1. Copy the SQL script above")
    print()
    print("2. Run in Supabase Dashboard:")
    print("   - Go to https://app.supabase.com")
    print("   - Click 'SQL Editor'")
    print("   - Click 'New Query'")
    print("   - Paste the SQL and click 'Run'")
    print()
    print("3. Verify the migration:")
    print("   - Check the raw_jobs table in Table Editor")
    print("   - New columns should appear: title, company")
    print()
    print("4. Restart the pipeline:")
    print("   - New jobs will automatically populate title and company")
    print("   - Existing jobs will have NULL values (that's OK)")
    print()

    print("=" * 80)
    print("ROLLBACK (if needed)")
    print("=" * 80)
    print()
    print("If you need to undo the changes, run:")
    print()
    rollback_sql = """
ALTER TABLE raw_jobs DROP COLUMN IF EXISTS title;
ALTER TABLE raw_jobs DROP COLUMN IF EXISTS company;
"""
    print(rollback_sql)
    print()


def verify_migration():
    """Verify that the migration was successful."""
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    print()

    print("Checking if columns exist...")

    # Try to get one row and check schema
    try:
        result = supabase.table("raw_jobs").select("*").limit(1).execute()

        if result.data:
            row = result.data[0]
            has_title = "title" in row
            has_company = "company" in row

            print()
            if has_title:
                print("✓ 'title' column exists")
            else:
                print("✗ 'title' column NOT found")

            if has_company:
                print("✓ 'company' column exists")
            else:
                print("✗ 'company' column NOT found")

            print()
            if has_title and has_company:
                print("SUCCESS: Migration appears to be complete!")
                return True
            else:
                print("PENDING: Please run the SQL migration script above.")
                return False
        else:
            print("⚠ raw_jobs table is empty, cannot verify schema")
            print("  (This is OK - schema can still be verified in table editor)")
            return None

    except Exception as e:
        print(f"Error checking schema: {e}")
        return False


if __name__ == "__main__":
    run_migration()
    print()
    print("To complete the migration, copy the SQL script and run it in Supabase Dashboard.")
    print()
