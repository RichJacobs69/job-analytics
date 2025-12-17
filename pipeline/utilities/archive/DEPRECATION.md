# Archived Utilities

This directory contains deprecated utility scripts that are no longer needed for pipeline operations. They are preserved for historical reference only.

## Deprecated Scripts

### `backfill_working_arrangement.py`
**Deprecated:** 2025-12-16
**Reason:** Pipeline classifier updated to handle working arrangement correctly

**What it did:**
- Reprocessed jobs with `working_arrangement='onsite'` to reclassify them
- Used pattern matching to detect remote/hybrid/onsite from job titles and descriptions
- Addressed issue where Adzuna's truncated descriptions caused false 'onsite' defaults

**Why it's no longer needed:**
1. **Classifier prompt updated** - Now returns 'unknown' instead of defaulting to 'onsite' when unclear
2. **Pipeline defaults changed** - Changed from `or 'onsite'` to `or 'unknown'` across all sources
3. **Honest data quality** - 67.6% 'unknown' rate reflects reality of truncated Adzuna text

**Future improvement:**
Pattern-based detection from this script should be integrated into the main pipeline as a pre-classification step to improve accuracy before LLM classification.

**Last run:** Should be run once on existing data before archival to update historical records

---

## Archive Policy

**When to archive utilities:**
- Feature is now handled by main pipeline
- One-time migration/backfill task is complete
- Script addressed a bug that has been fixed
- Functionality superseded by better approach

**What NOT to archive:**
- Active maintenance tools (check_pipeline_status.py, analyze_db_results.py)
- Error recovery tools (backfill_missing_enriched.py)
- Tools that run periodically (backfill_agency_flags.py)
