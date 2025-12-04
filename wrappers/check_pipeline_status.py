#!/usr/bin/env python3
"""
Wrapper script: Quick status check for the job classification pipeline.

Shows:
- Total jobs ingested (raw_jobs table)
- Total jobs classified (enriched_jobs table)
- Classification rate
- Breakdown by city
- Recent activity

Usage:
    python check_pipeline_status.py

Note: This is a wrapper around pipeline/utilities/check_pipeline_status.py
"""

import sys
from pathlib import Path

# Add project root to Python path for module imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    from pipeline.utilities.check_pipeline_status import main
    main()
