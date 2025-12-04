#!/usr/bin/env python3
"""
Wrapper script: Migrate raw_jobs table schema

Adds title and company columns to the raw_jobs table in Supabase.

Usage:
    python wrapper/migrate_raw_jobs_schema.py

This is a wrapper around pipeline/utilities/migrate_raw_jobs_schema.py
"""

import sys
from pathlib import Path

# Add project root to Python path for module imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    from pipeline.utilities.migrate_raw_jobs_schema import run_migration
    run_migration()
