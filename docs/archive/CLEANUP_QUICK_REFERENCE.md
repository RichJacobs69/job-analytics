# Cleanup Quick Reference Guide

**All 7 phases completed successfully on November 21, 2025**

---

## What Changed

### Deleted (3 directories, 2 files)
```
❌ migrations/                  (empty)
❌ other/                       (empty)
❌ docsdatabasemigrations/      (empty typo)
❌ backup/ directory            (outdated files)
❌ export_stripe_jobs.py        (test utility)
```

### Moved to `output/` (4 files)
```
📦 ats_analysis_results.json
📦 ats_test_results.json
📦 DOCUMENTATION_INDEX.md
📦 stripe_job_page.html
```

### Archived to `docs/archive/` (5 files)
```
📚 validate_all_greenhouse_companies.py
📚 phase1_ats_validation.py
📚 test_greenhouse_validation.py
📚 test_manual_insert.py
📚 test_skills_insert.py
```

### Created (5 new files)
```
✨ output/              (new directory for generated files)
✨ docs/README.md       (documentation index)
✨ docs/archive/README.md           (archive inventory)
✨ docs/archive/tests/README.md     (test inventory)
✨ CLEANUP_COMPLETE_SUMMARY.md      (detailed summary)
```

### Updated (1 file)
```
⚙️  .gitignore          (added output/ and generated files)
```

---

## Root Directory Now (Clean!)

| File | Purpose |
|------|---------|
| **CLAUDE.md** | Project development guide (START HERE) |
| **CLEANUP_COMPLETE_SUMMARY.md** | What was cleaned and why |
| **REPOSITORY_AUDIT_AND_RECOMMENDATIONS.md** | Detailed analysis & audit |
| **requirements.txt** | Python dependencies |
| **.env** | Configuration (secrets) |
| **.gitignore** | Git exclusions (UPDATED) |
| **agency_detection.py** | Agency filtering logic |
| **backfill_agency_flags.py** | Maintenance utility |
| **classifier.py** | Claude LLM integration |
| **db_connection.py** | Database wrapper |
| **fetch_jobs.py** | Pipeline orchestrator |
| **unified_job_ingester.py** | Multi-source merger |
| **validate_greenhouse_batched.py** | ATS validation (CURRENT) |
| **greenhouse_validation_results.json** | Validation results (24 companies) |
| **greenhouse_validation_results.csv** | Results export |

---

## Documentation Navigation

### For New Developers
1. Read: `CLAUDE.md` - Setup & architecture overview
2. Read: `docs/README.md` - Documentation index
3. Deep dive: Choose from `docs/` based on your role

### For Understanding the System
- `docs/system_architecture.yaml` - How it works
- `docs/schema_taxonomy.yaml` - How jobs are classified
- `docs/marketplace_questions.yaml` - Why we built this

### For Historical Context
- `docs/archive/README.md` - What was tried before
- `docs/archive/ATS_ANALYSIS_STRATEGIC_REPORT.md` - Why Greenhouse?
- `docs/archive/INDEPENDENT_SCRAPING_FEASIBILITY.md` - Why this approach?

---

## Directories at a Glance

```
config/            → Configuration files (company mappings, blacklists)
docs/              → Specifications & guides (READ THIS FIRST)
  ├── archive/     → Legacy docs & code (historical context)
  ├── database/    → Schema & migrations
  └── architecture/ → Deep-dive designs

output/            → Generated outputs (NOT version controlled)
scrapers/          → Data source integrations
  ├── adzuna/      → Adzuna API scraper
  └── greenhouse/  → Greenhouse web scraper

tests/             → Test suite
  ├── test_*_simple.py     → Unit tests
  ├── test_end_to_end.py   → Integration tests
  └── [others]             → Review flagged tests

__pycache__/       → Python cache (ignored)
```

---

## Key Files You'll Use

| File | When | Purpose |
|------|------|---------|
| `validate_greenhouse_batched.py` | Setup | Validate Greenhouse companies |
| `fetch_jobs.py` | Daily | Run the pipeline |
| `classifier.py` | Testing | Validate classification logic |
| `db_connection.py` | Development | Database operations |
| `config/company_ats_mapping.json` | Reference | Which companies to scrape |

---

## Git & Version Control

### These are NEW - don't commit
- `output/` directory → Gitignored
- `*.html` → Gitignored
- `*_results.json` → Gitignored

### These were DELETED - normal operation
- Old backup files
- Old validation scripts (archived in docs/)
- Empty directories

### No Functionality Broken
- All critical files preserved
- All working scripts still work
- Test suite still passes

---

## Verification Commands

```bash
# Check cleanup worked
ls -lah                      # Should show ~12 files
ls output/                   # Should show 4 generated files
ls docs/archive/             # Should show organized archives

# Verify scripts still work
python validate_greenhouse_batched.py --help
python fetch_jobs.py --help
python classifier.py         # Should run test mode

# Run tests
python -m pytest tests/
```

---

## If You Need Something

**"I need to set up my environment"**
→ Read: `CLAUDE.md` (requirements.txt section)

**"I need to understand the architecture"**
→ Read: `docs/README.md` → `docs/system_architecture.yaml`

**"I need to know why we chose Greenhouse"**
→ Read: `docs/archive/README.md` → `ATS_ANALYSIS_STRATEGIC_REPORT.md`

**"I need to add a new classification rule"**
→ Edit: `docs/schema_taxonomy.yaml` → Run tests

**"I need to see historical decisions"**
→ Browse: `docs/archive/` (all organized by topic)

**"I need to validate new companies"**
→ Run: `python validate_greenhouse_batched.py`

---

## Notes for Future Cleanups

- Generated outputs go in `output/` folder
- Old code goes in `docs/archive/` with context
- Document why things are archived in README files
- Update `.gitignore` for new output types
- Keep this quick reference updated

---

## Questions?

- Development setup: See `CLAUDE.md`
- Why we cleaned up: See `REPOSITORY_AUDIT_AND_RECOMMENDATIONS.md`
- What changed: See `CLEANUP_COMPLETE_SUMMARY.md`
- Project evolution: See `docs/archive/README.md`

**Status:** ✅ All cleanup complete, repository is clean and organized!
