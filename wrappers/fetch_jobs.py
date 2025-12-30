#!/usr/bin/env python3
"""
Wrapper script: Unified Job Fetcher - Multi-Source Pipeline Orchestrator

Purpose:
--------
Main entry point for fetching jobs from multiple sources:
- Adzuna API (aggregated job listings)
- Greenhouse scraper (direct ATS, Playwright-based)
- Lever API (direct ATS, HTTP API)
- Ashby API (direct ATS, HTTP API with structured compensation)

Orchestrates the full pipeline: fetch -> filter -> classify -> store.

Supports:
- Single or multi-source fetching (--sources adzuna,greenhouse,lever,ashby)
- Multiple cities (lon, nyc, den, sf, sin, etc.)
- Agency filtering (hard + soft detection)
- Classification via Gemini 2.5 Flash
- Storage in Supabase PostgreSQL

Usage:
------
# All sources:
python fetch_jobs.py --sources adzuna,greenhouse,lever,ashby

# Specific companies (applies to Greenhouse, Lever, Ashby):
python pipeline/fetch_jobs.py --sources greenhouse --companies stripe,gitlab

# Adzuna only:
python fetch_jobs.py lon 100 --sources adzuna

# Greenhouse only:
python fetch_jobs.py --sources greenhouse

# Lever only:
python fetch_jobs.py --sources lever

# Ashby only (best structured compensation data):
python fetch_jobs.py --sources ashby

# NYC with Adzuna + Greenhouse:
python fetch_jobs.py nyc 200 --sources adzuna,greenhouse

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
