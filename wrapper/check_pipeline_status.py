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

if __name__ == "__main__":
    from pipeline.utilities.check_pipeline_status import main
    main()
