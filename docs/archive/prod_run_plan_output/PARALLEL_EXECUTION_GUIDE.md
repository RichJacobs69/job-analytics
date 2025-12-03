# Parallel Execution Guide - Multiple Cities

**Date Updated:** 2025-12-02
**Purpose:** Simple guide for running parallel job fetches for multiple cities

## Quick Start

```powershell
cd "C:\Cursor Projects\job-analytics"

# Run all 3 cities in parallel (default: 100 jobs, both sources)
python run_all_cities.py

# Or specify max jobs and sources
python run_all_cities.py --max-jobs 100 --sources adzuna,greenhouse
python run_all_cities.py --max-jobs 50 --sources adzuna
```

That's it! The script handles everything:
- ✅ Starts all 3 cities (lon, nyc, den) simultaneously
- ✅ Prints progress for each city
- ✅ Waits for all to complete
- ✅ Reports results

## Examples

```powershell
# Default: 100 jobs, both Adzuna + Greenhouse
python run_all_cities.py

# Custom job count
python run_all_cities.py --max-jobs 200

# Adzuna only
python run_all_cities.py --sources adzuna

# Greenhouse only
python run_all_cities.py --sources greenhouse

# High volume with both sources
python run_all_cities.py --max-jobs 500 --sources adzuna,greenhouse
```

## Understanding Parallel Execution

When you run the script:
- **All 3 cities start simultaneously** - not one after another
- **Each runs in its own process** - independent and isolated
- **Different finish times** - depending on data volume and API responses
- **Progress printed separately** - you'll see output for each city

## Monitoring Progress

While cities are running, you'll see sections like:
```
============================================================
Starting: LON
Command: python fetch_jobs.py lon 100 --sources adzuna,greenhouse
============================================================

[... progress updates from London fetch ...]

✓ LON completed successfully
```

Each city prints its own progress independently. Just wait for all sections to complete.

## What If I Interrupt (Ctrl+C)?

The script will attempt to clean up processes. If you need to restart:

```powershell
# Just run the script again
python run_all_cities.py
```

## Rate Limiting

When running all 3 cities in parallel with `--sources adzuna,greenhouse`, you may see HTTP 429 "Too Many Requests" messages. This is **normal and expected**:
- 3 cities × 2 data sources = up to 6 concurrent classification processes
- Anthropic API has rate limits per minute
- The pipeline automatically retries with exponential backoff
- Jobs will complete successfully, just slower

If you want to avoid rate limits, run cities **sequentially instead:**

```powershell
python fetch_jobs.py lon 100 --sources adzuna,greenhouse
python fetch_jobs.py nyc 100 --sources adzuna,greenhouse
python fetch_jobs.py den 100 --sources adzuna,greenhouse
```

## Troubleshooting

### Script not found
```powershell
# Make sure you're in the project root directory
cd "C:\Cursor Projects\job-analytics"
dir run_all_cities.py  # Should show the file exists
python run_all_cities.py
```

### "fetch_jobs.py not found"
- Verify you're running from project root: `dir fetch_jobs.py`
- Python can't find the file if you're in a different directory

### One city fails, others continue
- If one city has an error, the script will still run the other two
- You'll see a message about which city failed
- Check the error output to debug

### Slow progress
- Initial startup takes ~20-30 seconds per city
- Rate limits may slow classification step (see "Rate Limiting" above)
- Greenhouse scraping takes longer than Adzuna API (normal)

## Command Line Options

```
--max-jobs NUM       Maximum jobs to fetch per city (default: 100)
--sources SOURCE     Data sources: adzuna, greenhouse, or adzuna,greenhouse
                     (default: adzuna,greenhouse)
```

## Related Files

- `run_all_cities.py` - The parallel execution script (this is what you run)
- `fetch_jobs.py` - Main pipeline that processes individual cities
- `CLAUDE.md` - Full development guide with all pipeline options

## Notes

- Python 3.x required
- Requirements.txt dependencies must be installed (`pip install -r requirements.txt`)
- .env file with API keys must be present
- Script uses Python's `multiprocessing` - fully parallel, not sequential

