#!/usr/bin/env python3
"""
Wrapper script: Analyze database results for today's pipeline run and overall totals.
Shows breakdown by city and job family.

Usage:
    python analyze_db_results.py

Note: This is a wrapper around pipeline/utilities/analyze_db_results.py
"""

import sys
from pathlib import Path

# Add project root to Python path for module imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    from pipeline.utilities.analyze_db_results import analyze_database
    analyze_database()
