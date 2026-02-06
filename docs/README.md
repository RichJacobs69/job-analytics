# Documentation Index

This directory contains all specifications, guides, and architectural documentation for the job-analytics platform.

> **For development setup, architecture implementation, and troubleshooting, see [`../CLAUDE.md`](../CLAUDE.md)** - It provides development commands, code walkthroughs, key implementation details, and solutions to common issues.

## Pipeline Status

| Pipeline | Schedule | Status |
|----------|----------|--------|
| Greenhouse | Mon/Tue/Thu/Fri 7AM UTC | ![Greenhouse](https://github.com/RichJacobs69/job-analytics/actions/workflows/scrape-greenhouse.yml/badge.svg) |
| Lever | Mon/Wed/Fri 6PM UTC | ![Lever](https://github.com/RichJacobs69/job-analytics/actions/workflows/scrape-lever.yml/badge.svg) |
| Ashby | Tue/Thu 6PM UTC | ![Ashby](https://github.com/RichJacobs69/job-analytics/actions/workflows/scrape-ashby.yml/badge.svg) |
| Workable | Wed/Sat 6PM UTC | ![Workable](https://github.com/RichJacobs69/job-analytics/actions/workflows/scrape-workable.yml/badge.svg) |
| Adzuna | Wed 7AM UTC | ![Adzuna](https://github.com/RichJacobs69/job-analytics/actions/workflows/scrape-adzuna.yml/badge.svg) |
| URL Validation | Mon-Fri 9AM UTC | ![Validation](https://github.com/RichJacobs69/job-analytics/actions/workflows/url-validation-stats.yml/badge.svg) |
| Employer Metadata | Sun 8AM UTC | ![Metadata](https://github.com/RichJacobs69/job-analytics/actions/workflows/refresh-employer-metadata.yml/badge.svg) |

**Live Dashboard:** [richjacobs.me/projects/hiring-market](https://richjacobs.me/projects/hiring-market)

## License

This project is provided for **portfolio viewing only**.

You are welcome to browse the code and run it locally to understand how it works, but **you may not copy, reuse, modify, or distribute any part of this code** without my prior written permission.

See [`LICENSE.md`](./LICENSE.md) for full details.

## Quick Start for New Developers

### First Steps
1. **[CLAUDE.md](../CLAUDE.md)** ← **Start here first!** Development setup, common commands, and architecture overview
2. Then return to this README to dive deep into specifications

### Understanding the Project
1. **marketplace_questions.md** - The "why": 35 key questions we're answering for job seekers and employers
2. **product_brief.md** - The "what": Product scope, KPIs, success metrics, and target markets
3. **schema_taxonomy.yaml** - The "how to classify": Job classification rules, extraction taxonomy, and data standards
4. **system_architecture.yaml** - The "how it works": System design, module interactions, and responsibilities

## Core Specifications

### Business & Product
- **marketplace_questions.md** - User research findings & marketplace question list
  - 35 questions across 7 categories (market demand, skills, compensation, location, etc.)
  - Guides all development priorities

- **product_brief.md** - Product specification & requirements
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

## Architecture Deep-Dives

### directory: `architecture/`
- **MULTI_SOURCE_PIPELINE.md** - Multi-source pipeline architecture (Adzuna, Greenhouse, Lever, Ashby, Workable)
- **INCREMENTAL_UPSERT_DESIGN.md** - Upsert-based deduplication and incremental processing
- **ADDING_NEW_LOCATIONS.md** - How to add new cities to the location system
- **SECURITY_AUDIT_REPORT.md** - Security assessment of the platform

### directory: `architecture/In Progress/`
- **EPIC_JOB_FEED.md** - Curated job feed (Phase 1-2 complete, Phase 3 TODO)

### directory: `architecture/Done/`
- **EPIC_WORKABLE_INTEGRATION.md** - Workable ATS integration (complete)
- **EPIC_EMPLOYER_ENRICHMENT.md** - Employer metadata enrichment (complete)

## Design Specifications

### directory: `design/`
- **JOB_FEED_UX_DESIGN.md** - Job feed UX specification (v1.5)
- **JOB_FEED_UX_REVIEW.md** - Design review and iteration log
- **job-feed-mockup.html** - Interactive HTML mockup

## Database Documentation

### directory: `database/`
- **migrations/** - SQL schema migrations (version controlled)
- **SCHEMA_UPDATES.md** - Changelog of database schema changes
  - Current tables: raw_jobs, enriched_jobs
  - Column definitions & constraints
  - Indexes for query performance

## Cost Tracking & Metrics

### directory: `costs/`
- **COST_METRICS.md** - Historical classification cost analysis (point-in-time snapshot from Dec 2025, pre-Gemini migration)
- CSV exports from early Claude Haiku era (archived for reference)

## Historical Archive

### directory: `archive/`
See **[archive/claude_archive.md](archive/claude_archive.md)** for documentation about previous iterations, analyses, and implementation decisions.

---

## Recommended Reading Order

**Getting Started (Everyone):**
1. **[../CLAUDE.md](../CLAUDE.md)** ← Start here for setup & architecture overview
2. marketplace_questions.md - The "why": business context
3. product_brief.md - The "what": product scope & KPIs

**Understanding Architecture (Developers):**
4. schema_taxonomy.yaml - How we classify jobs
5. system_architecture.yaml - System design & interactions
6. architecture/MULTI_SOURCE_PIPELINE.md - Multi-source pipeline design
7. architecture/INCREMENTAL_UPSERT_DESIGN.md - Deduplication strategy

**Implementation Details (When Needed):**
8. database/SCHEMA_UPDATES.md - Database schema & changes
9. blacklisting_process.md - Agency filtering & optimization
10. Individual module docstrings in source code

**Historical Context (Understanding Evolution):**
- archive/claude_archive.md - Why we chose certain approaches

---

## Contributing Guidelines

When updating documentation:
- Keep YAML specs current with code changes
- Document new features in appropriate section
- Add migrations to `database/migrations/` with descriptive names
- Update archive/claude_archive.md if moving docs to historical reference
- Keep this index up-to-date

### Epic Naming Convention

Epic documents in `docs/architecture/` follow this naming pattern:

```
EPIC_<NAME_IN_UPPERCASE>.md
```

Examples:
- `EPIC_EMPLOYER_METADATA.md`
- `EPIC_EXPERIENCE_RANGE_NORMALIZATION.md`
- `EPIC_JOB_FEED.md`
- `EPIC_ASHBY_INTEGRATION.md`

Rules:
- Prefix with `EPIC_`
- Use UPPERCASE with underscores
- End with `.md`
- Place in `docs/architecture/In Progress/` or `docs/architecture/Future Ideas/`

Questions? Check [../CLAUDE.md](../CLAUDE.md) in the project root for development setup and common tasks.
