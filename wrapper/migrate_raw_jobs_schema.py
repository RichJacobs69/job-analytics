#!/usr/bin/env python3
"""
Wrapper script: Migrate raw_jobs table schema

Adds title and company columns to the raw_jobs table in Supabase.

Usage:
    python wrapper/migrate_raw_jobs_schema.py

This is a wrapper around pipeline/utilities/migrate_raw_jobs_schema.py
"""

if __name__ == "__main__":
    from pipeline.utilities.migrate_raw_jobs_schema import run_migration
    run_migration()
