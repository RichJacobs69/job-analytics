#!/usr/bin/env python3
"""
Wrapper script: Unified Job Fetcher - Adzuna + Greenhouse Dual Pipeline Orchestrator

Purpose:
--------
Main entry point for fetching jobs from multiple sources (Adzuna API + Greenhouse scraper).
Orchestrates the full pipeline: fetch -> merge -> classify -> store.

Supports:
- Single or dual source fetching (--sources adzuna,greenhouse)
- Multiple cities (lon, nyc, den)
- Agency filtering (hard + soft detection)
- Classification via Claude 3.5 Haiku
- Storage in Supabase PostgreSQL

Usage:
------
# Dual pipeline (default):
python fetch_jobs.py lon 100 --sources adzuna,greenhouse

# Specific companies:
python pipeline/fetch_jobs.py --sources greenhouse --companies stripe,gitlab

# Adzuna only:
python fetch_jobs.py lon 100 --sources adzuna

# Greenhouse only (premium companies):
python fetch_jobs.py --sources greenhouse

# NYC with more jobs:
python fetch_jobs.py nyc 200 --sources adzuna,greenhouse

# With filtering:
python fetch_jobs.py lon 100 --sources adzuna,greenhouse --min-description-length 500

Author: Claude Code

Note: This is a wrapper around pipeline/fetch_jobs.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path for module imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    from pipeline.fetch_jobs import main
    asyncio.run(main())
