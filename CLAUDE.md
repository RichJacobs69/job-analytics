# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## IMPORTANT: No Emojis in Code or Documentation

**PROHIBITION:** Do NOT use any emojis in any code files, markdown files, or YAML configuration files.

**Reason:** Emoji characters can cause encoding issues on Windows systems.

**Use instead:** `[DONE]`, `[TODO]`, `[IN PROGRESS]`, `[WARNING]`, `[OK]`, `[NOT OK]`

## IMPORTANT: Use Skills When Relevant

Before starting any task, check if it matches a skill in `.claude/skills/`. If it does:
1. Invoke the skill immediately using the Skill tool
2. Follow the skill's documented steps exactly - do not improvise

| Skill | Trigger |
|-------|---------|
| `gha-analyzer` | Analyze GHA logs, debug workflows, check pipeline health |
| `company-curator` | Add/validate companies, check broken career pages |
| `config-validator` | Validate YAML/JSON, add skill/agency/location mappings |
| `data-analyst` | Create reports, analyze trends, generate content |
| `qa-tester` | Review test coverage, write tests, identify regressions |
| `repo-reviewer` | Audit repo, find duplication, identify stale files |
| `system-architect` | Plan features, review architecture decisions |
| `ux-designer` | Design UI components, review user flows |

> **For documentation navigation, see [`docs/README.md`](docs/README.md)**

## Project Overview

LLM-powered job market intelligence platform that fetches, classifies, and analyzes job postings. Ingests from Adzuna API + Greenhouse/Lever/Ashby scrapers, classifies via Gemini 2.5 Flash, stores in Supabase PostgreSQL.

**Live Dashboard:** [richjacobs.me/projects/hiring-market](https://richjacobs.me/projects/hiring-market)

**Status:**
- [DONE] Epics 1-7: Full pipeline operational, dashboard live, GitHub Actions automation
- [IN PROGRESS] Epic 8: Curated Job Feed (Phase 1 infrastructure complete)

**Dataset:** ~18,000+ enriched jobs across London, NYC, Denver, SF, Singapore

## Common Commands

```bash
# Pipeline execution
python wrappers/fetch_jobs.py --sources greenhouse           # Greenhouse only
python wrappers/fetch_jobs.py --sources lever                # Lever only
python wrappers/fetch_jobs.py --sources ashby                # Ashby only (best salary data)
python wrappers/fetch_jobs.py lon 100 --sources adzuna       # Adzuna only
python wrappers/fetch_jobs.py --sources adzuna,greenhouse,lever,ashby  # All sources

# With resume capability
python wrappers/fetch_jobs.py --sources greenhouse --resume-hours 24

# Derived data jobs (Epic 8 - Job Feed)
python pipeline/employer_stats.py              # Compute employer fill stats
python pipeline/summary_generator.py --limit=50 # Backfill summaries (new jobs get inline)
python pipeline/url_validator.py --limit=100   # Check for 404 dead links

# Utilities
python wrappers/check_pipeline_status.py
python wrappers/backfill_missing_enriched.py --dry-run

# ATS Company Discovery & Validation
python pipeline/utilities/discover_ats_companies.py all        # Discover new companies (Google CSE)
python pipeline/utilities/validate_ats_slugs.py greenhouse     # Validate all slugs for a source

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
Adzuna API ─────┐                    ┌───── Greenhouse/Lever/Ashby Scrapers
                │                    │
                v                    v
         unified_job_ingester.py (merge & dedupe)
                         │
                         v
              [Agency Blocklist Filter]
                         │
                         v
              classifier.py (Gemini 2.5 Flash)
                         │
                         v
              db_connection.py (Supabase: enriched_jobs)
                         │
         ┌───────────────┼───────────────┐
         v               v               v
  employer_stats.py  (inline summary)  url_validator.py
         │               │               │
         v               v               v
  employer_fill_stats  enriched_jobs   url_status
                       .summary
                         │
                         v
              Next.js Dashboard + Job Feed API
```

## Directory Structure

See [`docs/REPOSITORY_STRUCTURE.md`](docs/REPOSITORY_STRUCTURE.md) for full details.

```
job-analytics/
├── wrappers/          # Entry points (thin wrappers)
├── pipeline/          # Core production code
│   └── utilities/     # Backfill & maintenance
├── scrapers/          # Adzuna, Greenhouse, Lever, Ashby
├── config/            # YAML/JSON configs
│   ├── greenhouse/    # Greenhouse-specific
│   ├── lever/         # Lever-specific
│   └── ashby/         # Ashby-specific
├── docs/              # Documentation
└── tests/             # Test suite
```

## Core Modules

| Module | Purpose |
|--------|---------|
| `pipeline/fetch_jobs.py` | Main orchestrator, coordinates sources |
| `pipeline/classifier.py` | Gemini LLM integration, extracts structured data |
| `pipeline/db_connection.py` | Supabase client, deduplication |
| `pipeline/location_extractor.py` | Pattern-based location extraction |
| `pipeline/agency_detection.py` | Agency filtering (hard + soft) |
| `pipeline/employer_stats.py` | Median fill times per employer (Epic 8) |
| `pipeline/summary_generator.py` | Backfill utility for summaries (new jobs get inline via classifier) |
| `pipeline/url_validator.py` | 404 detection for dead links (Epic 8) |
| `scrapers/greenhouse/greenhouse_scraper.py` | Playwright browser automation |
| `scrapers/lever/lever_fetcher.py` | Lever API client |
| `scrapers/ashby/ashby_fetcher.py` | Ashby API client (structured compensation) |

## Config Structure

```
config/
├── greenhouse/
│   ├── company_ats_mapping.json    # 401 companies (with url_type for embed/eu)
│   ├── title_patterns.yaml         # Role filtering
│   └── location_patterns.yaml      # City filtering
├── lever/
│   ├── company_mapping.json        # 121 companies
│   ├── title_patterns.yaml
│   └── location_patterns.yaml
├── ashby/
│   ├── company_mapping.json        # 69 companies
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

## Current Work: Epic 8 Job Feed

**Phase 1 (Infrastructure) - COMPLETE:**
- Database: `employer_fill_stats`, `enriched_jobs.summary` column, `url_status` column
- Pipeline: Summaries generated inline during classification (not batch)
- API: `/api/hiring-market/jobs/feed`, `/api/hiring-market/jobs/[id]/context`
- GitHub Actions: `refresh-derived-tables.yml` (URL validation + employer stats only)

**Phase 2 (Frontend) - TODO:**
- Job feed page at `/projects/hiring-market/jobs`
- Filter components, expandable job cards

**See:** `docs/architecture/In Progress/EPIC_JOB_FEED.md`

## GitHub Actions Workflows

Located in `.github/workflows/`:
- `scrape-greenhouse.yml` - Mon/Wed/Fri/Sun 7AM UTC (4 batches, ~100 companies each)
- `scrape-adzuna.yml` - Tue/Thu/Sat 7AM UTC (5 cities)
- `scrape-lever.yml` - Sun/Mon/Wed/Fri 6PM UTC (evening slot)
- `scrape-ashby.yml` - Tue/Thu/Sat 6PM UTC (evening slot)
- `refresh-derived-tables.yml` - Mon-Thu 9AM UTC (URL validation + employer stats)

## Key References

| Doc | Purpose |
|-----|---------|
| `docs/README.md` | Documentation index |
| `docs/REPOSITORY_STRUCTURE.md` | Directory organization |
| `docs/architecture/MULTI_SOURCE_PIPELINE.md` | Full pipeline architecture |
| `docs/schema_taxonomy.yaml` | Classification rules |
| `docs/architecture/ADDING_NEW_LOCATIONS.md` | Location system guide |
| `docs/architecture/Future Ideas/EPIC_JOB_FEED.md` | Job feed epic (current work) |

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
