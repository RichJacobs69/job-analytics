#!/usr/bin/env python3
"""
Wrapper script: Unified Job Fetcher - Multi-Source Pipeline Orchestrator

Purpose:
--------
Main entry point for fetching jobs from multiple ATS sources:
- Greenhouse API (direct ATS, REST API)
- Lever API (direct ATS, HTTP API)
- Ashby API (direct ATS, HTTP API with structured compensation)
- Workable API (direct ATS, workplace_type)
- SmartRecruiters API (direct ATS, locationType, experienceLevel)

Orchestrates the full pipeline: fetch -> filter -> classify -> store.

Supports:
- Single or multi-source fetching (--sources greenhouse,lever,ashby,workable,smartrecruiters)
- Multiple cities (lon, nyc, den, sf, sin, etc.)
- Agency filtering (hard + soft detection)
- Classification via Gemini 2.5 Flash
- Storage in Supabase PostgreSQL

Usage:
------
# All sources:
python fetch_jobs.py --sources greenhouse,lever,ashby,workable,smartrecruiters

# Specific companies (applies to Greenhouse, Lever, Ashby):
python pipeline/fetch_jobs.py --sources greenhouse --companies stripe,gitlab

# Greenhouse only:
python fetch_jobs.py --sources greenhouse

# Lever only:
python fetch_jobs.py --sources lever

# Ashby only (best structured compensation data):
python fetch_jobs.py --sources ashby

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
