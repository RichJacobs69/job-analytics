# Working Arrangement Classification - Architectural Changes

**Date:** 2025-12-16
**Status:** [DONE]

## Problem Statement

The pipeline was instructing the LLM to default to 'onsite' when working arrangement couldn't be determined from job descriptions. This created **false confidence** in the data:

- Adzuna jobs have truncated descriptions (~200 chars)
- Working arrangement info was cut off
- LLM had no information but was told to guess 'onsite'
- Result: 80.5% jobs marked as 'unknown' (LLM ignored instruction), but architecture was dishonest

## Changes Made

### 1. Classifier Prompt (`pipeline/classifier.py`)

**Before:**
```python
"working_arrangement": "onsite|hybrid|remote|flexible (required - default: onsite if not stated)"

# WORKING ARRANGEMENT GUIDANCE
- "Remote or hybrid" → flexible
- "Hybrid (2 days office)" → hybrid
- "Remote-first" → remote
- Nothing stated → onsite
```

**After:**
```python
"working_arrangement": "onsite|hybrid|remote|flexible|unknown (required - use 'unknown' if not stated or unclear)"

# WORKING ARRANGEMENT GUIDANCE
- "Remote or hybrid" → flexible
- "Hybrid (2 days office)" → hybrid
- "Remote-first" → remote
- "Office-based" or "Onsite" explicitly stated → onsite
- Nothing stated or truncated text → unknown
```

### 2. Pipeline Defaults (`pipeline/fetch_jobs.py`)

**Before:**
```python
working_arrangement=location.get('working_arrangement') or 'onsite',
```

**After:**
```python
working_arrangement=location.get('working_arrangement') or 'unknown',
```

Changed in 4 locations:
- `process_adzuna_incremental()` (line 520)
- `process_greenhouse_incremental()` (line 870)
- `process_lever_incremental()` (line 1154)
- Helper function (line 1418)

### 3. Backfill Script (`pipeline/utilities/backfill_missing_enriched.py`)

**Before:**
```python
working_arrangement=location.get('working_arrangement') or 'onsite',
```

**After:**
```python
working_arrangement=location.get('working_arrangement') or 'unknown',
```

### 4. Deprecated Utility

**Archived:** `pipeline/utilities/backfill_working_arrangement.py` → `archive/`
- Added deprecation notice to file header
- Created `archive/DEPRECATION.md` documentation
- Script no longer needed since classifier now returns honest 'unknown' values

## Current Data Quality (as of 2025-12-16)

| Working Arrangement | Count | % of Total |
|---|---|---|
| **unknown** | 5,861 | 67.6% |
| hybrid | 1,352 | 15.6% |
| remote | 778 | 9.0% |
| flexible | 318 | 3.7% |
| onsite | 361 | 4.2% |

### By Data Source:

**Adzuna (7,193 jobs):**
- 80.5% unknown ← **Honest reflection of truncated text**
- Only 11.1% hybrid, 6.1% remote

**Greenhouse (1,243 jobs):**
- 5.8% unknown ← **Full text allows accurate classification**
- 40.3% hybrid, 22.4% remote

**Lever (232 jobs):**
- 0% unknown ← **Perfect classification with full text**
- 41.4% onsite, 25.0% remote, 22.0% hybrid

## Impact

### Positive Changes [DONE]
1. **Honest data quality** - 'unknown' reflects reality of truncated Adzuna text
2. **No false confidence** - Not claiming to know what we don't know
3. **Consistent defaults** - 'unknown' across all pipeline entry points
4. **Simplified codebase** - Removed backfill utility that's no longer needed

### Remaining Issues [NEEDS ATTENTION]
1. **80.5% unknown rate on Adzuna** - Still a data quality problem
2. **No pattern-based detection** - Could improve unknown rate to ~40% with title pattern matching

## Future Improvements

### Recommended: Pattern-First Hybrid Approach

1. **Extract pattern logic** to `pipeline/working_arrangement_detector.py`:
   ```python
   def detect_working_arrangement(title: str, description: str) -> str | None:
       # Patterns from archived backfill script
       # Returns: 'remote' | 'hybrid' | 'onsite' | None
   ```

2. **Integrate at pipeline ingestion** (before LLM classification):
   ```python
   pattern_result = detect_working_arrangement(job.title, job.description)
   if pattern_result:
       working_arrangement = pattern_result  # Free, instant, deterministic
   else:
       # Fall back to LLM for full-text sources only
       working_arrangement = location.get('working_arrangement') or 'unknown'
   ```

3. **Benefits:**
   - 90% cost reduction (patterns handle most cases)
   - Adzuna: 80% unknown → ~40% unknown
   - Greenhouse/Lever: Keep LLM nuance for complex descriptions
   - Fully deprecate backfill utility

## Testing Recommendations

1. **Run classifier on sample batch** - Verify 'unknown' is returned for truncated text
2. **Check new ingestions** - Ensure 'onsite' only appears when explicitly stated
3. **Monitor distribution** - Track working_arrangement breakdown over next week

## References

- Classifier implementation: `pipeline/classifier.py`
- Pipeline integration: `pipeline/fetch_jobs.py`
- Archived utility: `pipeline/utilities/archive/backfill_working_arrangement.py`
- Deprecation docs: `pipeline/utilities/archive/DEPRECATION.md`
