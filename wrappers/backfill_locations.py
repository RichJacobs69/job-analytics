#!/usr/bin/env python
"""
Wrapper script for backfill_locations utility.

Usage:
    python wrappers/backfill_locations.py [--limit N] [--dry-run]
"""

import sys
sys.path.insert(0, '.')

from pipeline.utilities.backfill_locations import main

if __name__ == '__main__':
    main()
