# Documentation Index

This directory contains all specifications, guides, and architectural documentation for the job-analytics platform.

> **⚙️ For development setup, architecture implementation, and troubleshooting, see [`../CLAUDE.md`](../CLAUDE.md)** - It provides development commands, code walkthroughs, key implementation details, and solutions to common issues.

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

## Database Documentation

### directory: `database/`
- **migrations/** - SQL schema migrations (version controlled)
- **SCHEMA_UPDATES.md** - Changelog of database schema changes
  - Current tables: raw_jobs, enriched_jobs
  - Column definitions & constraints
  - Indexes for query performance

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

**Implementation Details (When Needed):**
7. database/SCHEMA_UPDATES.md - Database schema & changes
8. blacklisting_process.md - Agency filtering & optimization
9. Individual module docstrings in source code (../classifier.py, ../db_connection.py, etc.)

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
