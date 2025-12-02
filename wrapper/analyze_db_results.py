#!/usr/bin/env python3
"""
Wrapper script: Analyze database results for today's pipeline run and overall totals.
Shows breakdown by city and job family.

Usage:
    python analyze_db_results.py

Note: This is a wrapper around pipeline/utilities/analyze_db_results.py
"""

if __name__ == "__main__":
    from pipeline.utilities.analyze_db_results import analyze_database
    analyze_database()
