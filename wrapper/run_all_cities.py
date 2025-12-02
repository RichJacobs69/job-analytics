#!/usr/bin/env python3
"""
Wrapper script: Parallel execution runner for fetching jobs from multiple cities simultaneously.

Usage:
    python run_all_cities.py --max-jobs 100 --sources adzuna,greenhouse
    python run_all_cities.py                    # Uses defaults: 100 jobs, adzuna+greenhouse

This script runs fetch_jobs.py for London, NYC, and Denver in parallel using
Python's multiprocessing, significantly reducing total execution time.

Note: This is a wrapper around pipeline/run_all_cities.py
"""

if __name__ == "__main__":
    from pipeline.run_all_cities import main
    main()
