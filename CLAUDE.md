# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## IMPORTANT: No Emojis in Code or Documentation

**PROHIBITION:** Do NOT use any emojis in any code files, markdown files, or YAML configuration files.

**Reason:** Emoji characters can cause encoding issues on Windows systems.

**Use instead:** `[DONE]`, `[TODO]`, `[IN PROGRESS]`, `[WARNING]`, `[OK]`, `[NOT OK]`

> **For documentation navigation, see [`docs/README.md`](docs/README.md)**

## Project Overview

LLM-powered job market intelligence platform that fetches, classifies, and analyzes job postings using Claude AI. Ingests from Adzuna API + Greenhouse/Lever scrapers, classifies via Claude 3.5 Haiku, stores in Supabase PostgreSQL.

**Live Dashboard:** [richjacobs.me/projects/hiring-market](https://richjacobs.me/projects/hiring-market)

**Status:**
- [DONE] Epics 1-6: Full pipeline operational, dashboard live
- [IN PROGRESS] Epic 7: GitHub Actions automation

**Dataset:** ~6,000+ enriched jobs across London, NYC, Denver, SF, Singapore

## Common Commands

```bash
# Pipeline execution
python wrappers/fetch_jobs.py --sources greenhouse           # Greenhouse only
python wrappers/fetch_jobs.py --sources lever                # Lever only
python wrappers/fetch_jobs.py lon 100 --sources adzuna       # Adzuna only
python wrappers/fetch_jobs.py --sources adzuna,greenhouse    # Dual pipeline

# With resume capability
python wrappers/fetch_jobs.py --sources greenhouse --resume-hours 24

# Utilities
python wrappers/check_pipeline_status.py
python wrappers/backfill_missing_enriched.py --dry-run

# Tests
pytest tests/ -v
```

## CRITICAL: Long-Running Command Protocol

**For commands >5 minutes:**
1. Use `run_in_background: true` in Bash tool
2. Save the shell ID immediately
3. Use `TaskOutput` to check progress
4. Create a TodoWrite entry to track

## Environment Variables

Required in `.env`:
```
ADZUNA_APP_ID=<app_id>
ADZUNA_API_KEY=<api_key>
ANTHROPIC_API_KEY=<key>
SUPABASE_URL=<url>
SUPABASE_KEY=<key>
```

## Architecture

```
Adzuna API ─────┐                    ┌───── Greenhouse Scraper
                │                    │
                v                    v
         unified_job_ingester.py (merge & dedupe)
                         │
                         v
              [Agency Blocklist Filter]
                         │
                         v
              classifier.py (Claude Haiku)
                         │
                         v
              db_connection.py (Supabase)
                         │
                         v
              Next.js Dashboard (richjacobs.me)
```

## Directory Structure

See [`docs/REPOSITORY_STRUCTURE.md`](docs/REPOSITORY_STRUCTURE.md) for full details.

```
job-analytics/
├── wrappers/          # Entry points (thin wrappers)
├── pipeline/          # Core production code
│   └── utilities/     # Backfill & maintenance
├── scrapers/          # Adzuna, Greenhouse, Lever
├── config/            # YAML/JSON configs
│   ├── greenhouse/    # Greenhouse-specific
│   └── lever/         # Lever-specific
├── docs/              # Documentation
└── tests/             # Test suite
```

## Core Modules

| Module | Purpose |
|--------|---------|
| `pipeline/fetch_jobs.py` | Main orchestrator, coordinates sources |
| `pipeline/classifier.py` | Claude LLM integration, extracts structured data |
| `pipeline/db_connection.py` | Supabase client, deduplication |
| `pipeline/location_extractor.py` | Pattern-based location extraction |
| `pipeline/agency_detection.py` | Agency filtering (hard + soft) |
| `scrapers/greenhouse/greenhouse_scraper.py` | Playwright browser automation |
| `scrapers/lever/lever_fetcher.py` | Lever API client |

## Config Structure

```
config/
├── greenhouse/
│   ├── company_ats_mapping.json    # 302 companies
│   ├── title_patterns.yaml         # Role filtering
│   └── location_patterns.yaml      # City filtering
├── lever/
│   ├── company_mapping.json        # 61 companies
│   ├── title_patterns.yaml
│   └── location_patterns.yaml
├── location_mapping.yaml           # Master location config
├── agency_blacklist.yaml           # Recruitment firm blocklist
└── job_family_mapping.yaml         # Subfamily -> family mapping
```

## Location System

Uses JSONB array for flexible multi-location support:
```json
[{"type": "city", "country_code": "US", "city": "new_york"}]
[{"type": "remote", "scope": "global"}]
```

**Adding locations:** See `docs/architecture/ADDING_NEW_LOCATIONS.md`

## Cost Optimization

- **Pre-filters:** Title + location filtering achieves 94.7% reduction before LLM
- **Cost per job:** $0.00388 (Claude Haiku)
- **Agency blocklist:** Blocks 10-15% before classification

## Current Work: Epic 7 Automation

GitHub Actions workflows in `.github/workflows/`:
- `scrape-greenhouse.yml` - Daily batched (Mon-Thu)
- `scrape-lever.yml` - Weekly
- `scrape-adzuna.yml` - Daily

**See:** `docs/epic7_automation_planning.md` for full details

## Key References

| Doc | Purpose |
|-----|---------|
| `docs/README.md` | Documentation index |
| `docs/REPOSITORY_STRUCTURE.md` | Directory organization |
| `docs/architecture/MULTI_SOURCE_PIPELINE.md` | Full pipeline architecture (Adzuna + Greenhouse + Lever) |
| `docs/schema_taxonomy.yaml` | Classification rules |
| `docs/architecture/ADDING_NEW_LOCATIONS.md` | Location system guide |
| `docs/epic7_automation_planning.md` | Current automation work |

## Troubleshooting

**Supabase 1000-row limit:** All queries MUST paginate:
```python
offset = 0
while True:
    batch = supabase.table('t').select('*').offset(offset).limit(1000).execute()
    if not batch.data: break
    offset += 1000
```

**Classification issues:** Check if text is truncated (Adzuna limitation)

**Agency spam:** Add to `config/agency_blacklist.yaml`, run backfill

---

**Historical content archived:** `docs/archive/claude_archive.md`
