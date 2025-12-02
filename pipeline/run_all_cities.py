#!/usr/bin/env python3
"""
Parallel execution runner for fetching jobs from multiple cities simultaneously.

Usage:
    python run_all_cities.py --max-jobs 100 --sources adzuna,greenhouse
    python run_all_cities.py                    # Uses defaults: 100 jobs, adzuna+greenhouse

This script runs fetch_jobs.py for London, NYC, and Denver in parallel using
Python's multiprocessing, significantly reducing total execution time.
"""

import subprocess
import sys
import argparse
from multiprocessing import Process
from pathlib import Path


def run_city(city: str, max_jobs: int, sources: str) -> None:
    """Run fetch_jobs.py for a single city."""
    cmd = ["python", "pipeline/fetch_jobs.py", city, str(max_jobs), "--sources", sources]

    print(f"\n{'='*60}")
    print(f"Starting: {city.upper()}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")

    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n✓ {city.upper()} completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ {city.upper()} failed with exit code {e.returncode}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Run fetch_jobs.py for all cities (lon, nyc, den) in parallel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all_cities.py
  python run_all_cities.py --max-jobs 100
  python run_all_cities.py --max-jobs 100 --sources adzuna
  python run_all_cities.py --max-jobs 100 --sources adzuna,greenhouse
        """
    )

    parser.add_argument(
        "--max-jobs",
        type=int,
        default=100,
        help="Maximum jobs to fetch per city (default: 100)"
    )

    parser.add_argument(
        "--sources",
        default="adzuna,greenhouse",
        help="Data sources to use: adzuna, greenhouse, or adzuna,greenhouse (default: adzuna,greenhouse)"
    )

    args = parser.parse_args()

    # Verify fetch_jobs.py exists
    if not Path("pipeline/fetch_jobs.py").exists():
        print("Error: pipeline/fetch_jobs.py not found")
        print("Please run this script from the job-analytics project root directory")
        sys.exit(1)

    cities = ["lon", "nyc", "den"]

    print("\n" + "="*60)
    print("PARALLEL JOB FETCH FOR ALL CITIES")
    print("="*60)
    print(f"Cities: {', '.join(cities)}")
    print(f"Max jobs per city: {args.max_jobs}")
    print(f"Sources: {args.sources}")
    print(f"Total execution will run all 3 cities simultaneously")
    print("="*60 + "\n")

    # Start all cities in parallel
    processes = []
    for city in cities:
        p = Process(target=run_city, args=(city, args.max_jobs, args.sources))
        p.start()
        processes.append(p)

    # Wait for all processes to complete
    print("Waiting for all cities to complete...\n")
    for p in processes:
        p.join()

    print("\n" + "="*60)
    print("ALL CITIES COMPLETED")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
