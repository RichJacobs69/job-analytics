# Documentation Index

This directory contains all specifications, guides, and architectural documentation for the job-analytics platform.

> **⚙️ For development setup, architecture implementation, and troubleshooting, see [`../CLAUDE.md`](../CLAUDE.md)** - It provides development commands, code walkthroughs, key implementation details, and solutions to common issues.

## License

This project is provided for **portfolio viewing only**.

You are welcome to browse the code and run it locally to understand how it works, but **you may not copy, reuse, modify, or distribute any part of this code** without my prior written permission.

See [`LICENSE.md`](./LICENSE.md) for full details.

## Quick Start for New Developers

### First Steps
1. **[CLAUDE.md](../CLAUDE.md)** ← **Start here first!** Development setup, common commands, and architecture overview
2. Then return to this README to dive deep into specifications

### Understanding the Project
1. **marketplace_questions.yaml** - The "why": 35 key questions we're answering for job seekers and employers
2. **product_brief.yaml** - The "what": Product scope, KPIs, success metrics, and target markets
3. **schema_taxonomy.yaml** - The "how to classify": Job classification rules, extraction taxonomy, and data standards
4. **system_architecture.yaml** - The "how it works": System design, module interactions, and responsibilities

## Core Specifications

### Business & Product
- **marketplace_questions.yaml** - User research findings & marketplace question list
  - 35 questions across 7 categories (market demand, skills, compensation, location, etc.)
  - Guides all development priorities

- **product_brief.yaml** - Product specification & requirements
  - Scope: 3 cities (London, NYC, Denver)
  - 12 job titles across Data & Product families
  - Success metrics: coverage, freshness, reliability, latency

### Technical Specifications
- **schema_taxonomy.yaml** - Complete classification ontology
  - Job function families & subfamilies
  - Seniority levels (Junior → Staff+)
  - Skills taxonomy (Programming, ML, Cloud, etc.)
  - Work arrangements & compensation extraction rules

- **system_architecture.yaml** - System design document
  - High-level architecture diagram
  - Module responsibilities & interactions
  - Data flow: Adzuna → Greenhouse → Classifier → Database → Analytics
  - Cost optimization strategies

## Reference Guides

- **blacklisting_process.md** - How agency detection works
  - Hard filtering (pre-LLM) vs. soft detection (post-classification)
  - Blacklist maintenance process
  - Current effectiveness metrics

- **pipeline_flow** - ASCII diagram of data pipeline flow

## Architecture Deep-Dives

### directory: `architecture/`
- **DUAL_PIPELINE.md** - Detailed design of Adzuna + Greenhouse dual data sources
  - How jobs are merged and deduplicated
  - Why dual sources provide better coverage

## Analytics & Consumption Layer

- **epic5_analytics_layer_planning.md** - Job Market Dashboard delivery plan (ACTIVE)
  - Status: **Phase 0 Complete** ✅ (2025-12-08)
  - Building Next.js dashboard at `richjacobs.me/projects/job-market`
  - Architecture: Next.js API Routes → Supabase (read-only)
  - Chart library: Chart.js
  - 6 phased delivery (Foundation → Launch)

## Database Documentation

### directory: `database/`
- **migrations/** - SQL schema migrations (version controlled)
- **SCHEMA_UPDATES.md** - Changelog of database schema changes
  - Current tables: raw_jobs, enriched_jobs
  - Column definitions & constraints
  - Indexes for query performance

## Cost Tracking & Metrics

### directory: `costs/`
- **COST_METRICS.md** - Classification cost analysis and optimization strategies
  - Current cost per job: ~$0.006 per raw insert, ~$0.01 per classified job
  - Token usage breakdowns
  - Historical cost data
  
- **claude_api_cost_*.csv** - Daily cost exports from Anthropic dashboard
- **claude_api_tokens_*.csv** - Hourly token usage exports

**Key Metrics:**
| Metric | Value | Timestamp |
|--------|-------|-----------|
| Cost per raw insert | $0.00567 | 2025-12-04 (point-in-time) |
| Cost per classified job | $0.00976 | 2025-12-04 (point-in-time) |
| Classification rate | 58% | 2025-12-04 (point-in-time) |
| Model | Claude 3.5 Haiku | - |
| **Current dataset size** | 5,629 enriched jobs | 2025-12-07 (Supabase) |
| **Companies configured** | 302 Greenhouse companies | 2025-12-07 (config) |

## Testing Documentation

### directory: `testing/`
- **GREENHOUSE_VALIDATION.md** - Results and methodology of Greenhouse scraper testing
  - 24 verified companies with active Greenhouse presence
  - 1,045 total job postings captured
  - Validation metrics and coverage analysis

## Historical Archive

### directory: `archive/`
See **archive/README.md** for documentation about previous iterations, analyses, and implementation decisions.

This is valuable context for understanding how the system evolved, why certain decisions were made, and what was tried before.

---

## Recommended Reading Order

**Getting Started (Everyone):**
1. **[../CLAUDE.md](../CLAUDE.md)** ← Start here for setup & architecture overview
2. marketplace_questions.yaml - The "why": business context
3. product_brief.yaml - The "what": product scope & KPIs

**Understanding Architecture (Developers):**
4. schema_taxonomy.yaml - How we classify jobs
5. system_architecture.yaml - System design & interactions
6. architecture/DUAL_PIPELINE.md - Adzuna + Greenhouse pipeline design
7. **epic5_analytics_layer_planning.md** - Analytics dashboard architecture (active development)

**Implementation Details (When Needed):**
8. database/SCHEMA_UPDATES.md - Database schema & changes
9. blacklisting_process.md - Agency filtering & optimization
10. Individual module docstrings in source code (../classifier.py, ../db_connection.py, etc.)

**Historical Context (Understanding Evolution):**
- archive/README.md - Why we chose certain approaches

---

## Contributing Guidelines

When updating documentation:
- Keep YAML specs current with code changes
- Document new features in appropriate section
- Add migrations to `database/migrations/` with descriptive names
- Update archive README if moving docs to historical reference
- Keep this index up-to-date

Questions? Check [../CLAUDE.md](../CLAUDE.md) in the project root for development setup and common tasks.
