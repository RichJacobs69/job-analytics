# Repository Cleanup Plan - November 24, 2025

## Current Status Summary

**✅ COMPLETED:**
- Epic 1: Data Ingestion Pipeline (Adzuna + Greenhouse dual-source)
- Epic 2: Job Classification & Enrichment (Claude 3.5 Haiku)
- Epic 3: Database & Data Layer (Supabase PostgreSQL)
- Adzuna Integration: Fixed and tested (3 bugs resolved)
- Greenhouse Integration: Operational (24 verified companies, 1,045 jobs)
- E2E Pipeline: Verified working end-to-end

**🔴 BLOCKED:**
- Epic 4: Pipeline Validation & Economics (needs `validate_pipeline.py` run)

**⏳ PLANNED:**
- Epic 5: Analytics Query Layer
- Epic 6: Dashboard & Visualization
- Epic 7: Automation & Operational Excellence

---

## 1. Documentation Files to Update

### High Priority - Core Documentation

#### ✅ CLAUDE.md (Main development guide)
**Status:** Needs epic status update
**Updates needed:**
- Mark Epic 1-3 as COMPLETE
- Update Adzuna integration status (fixed, tested, working)
- Add note about Nov 24 fixes (dict-to-UnifiedJob conversion)
- Update Epic 4 as next priority

#### ✅ docs/system_architecture.yaml
**Status:** Needs pipeline status update
**Updates needed:**
- Update dual-pipeline status to "operational"
- Add Adzuna integration details
- Note agency filtering working (hard + soft)
- Update cost per job: $0.00168 (verified)

#### ✅ docs/product_brief.yaml
**Status:** Review for accuracy
**Updates needed:**
- Confirm Epic 1-3 completion
- Update timeline/roadmap if present

#### ⚠️ FIXES_APPLIED_2025-11-24.md
**Status:** Move to docs/archive/
**Reason:** Completed fixes, keep for reference but archive

---

## 2. Test Files - Cleanup Strategy

### A. Root-Level Test Files (ARCHIVE)

**Move to `docs/archive/tests/`:**

```
test_classify_only.py            → One-off classification test
test_dedupe_only.py              → One-off dedup test
test_greenhouse_only.py          → Superseded by test_greenhouse_scraper_simple.py
test_insert_greenhouse.py        → One-off insertion test
test_store_only.py               → One-off storage test
test_unified_job_fix.py          → Verification test for Nov 24 fix (keep as reference)
test_pipeline_integration.py     → Integration test (keep for reference)
test_database_insertion.py       → DB test (keep for reference)
```

**KEEP (potentially useful for validation):**
```
test_full_pipeline_scale.py      → Scale testing - useful for Epic 4 validation
```

### B. Active Test Suite (tests/ directory)

**KEEP - Active tests:**
```
tests/test_greenhouse_scraper_simple.py   → Core scraper test
tests/test_two_companies.py               → Multi-company test
tests/test_end_to_end.py                  → E2E validation
tests/test_ats_scraping.py                → ATS validation
tests/test_orchestrator.py                → Pipeline orchestration test
tests/test_failed_job.py                  → Error handling test
```

---

## 3. JSON/CSV Output Files - Cleanup

### A. Validation Outputs (CONSOLIDATE)

**Current files:**
```
validation_metrics.json
validation_metrics_debug.json
validation_metrics_fast.json
validation_metrics_adzuna_only.json
validation_metrics_full_pipeline.json
validation_test.json
validation_both_sources.json
```

**Action:** Move to `output/validation_history/` except:
- Keep: `validation_metrics_full_pipeline.json` (most comprehensive)
- Archive rest as historical

### B. Test Outputs (ARCHIVE)

**Move to `output/test_outputs/`:**
```
test_merged_jobs.json
test_classified_jobs.json
test_greenhouse_jobs.json
```

### C. Keep Active
```
greenhouse_validation_results.json       → ATS validation results
greenhouse_validation_results.csv        → Same, CSV format
config/company_ats_mapping.json          → Active config
```

---

## 4. Documentation Archive Review

### Files in docs/archive/ (KEEP - Historical Reference)

**Already archived correctly:**
```
docs/archive/ATS_SCRAPING_GUIDE.md
docs/archive/FINDINGS_AND_RECOMMENDATION.md
docs/archive/INDEED_VS_ADZUNA_COMPARISON.md
docs/archive/ATS_ANALYSIS_STRATEGIC_REPORT.md
docs/archive/INDEPENDENT_SCRAPING_FEASIBILITY.md
docs/archive/HYBRID_SCRAPING_IMPLEMENTATION_COMPLETE.md
docs/archive/ATS_SCRAPING_TEST_RESULTS.md
docs/archive/GREENHOUSE_SCRAPER_STATUS.md
docs/archive/IMPLEMENTATION_COMPLETE.md
docs/archive/REPOSITORY_AUDIT_AND_RECOMMENDATIONS.md
docs/archive/CLEANUP_COMPLETE_SUMMARY.md
docs/archive/CLEANUP_QUICK_REFERENCE.md
```

**Action:** These are fine, no changes needed.

---

## 5. Active Documentation (KEEP & MAINTAIN)

```
docs/README.md                           → Documentation index
docs/blacklisting_process.md             → Agency detection methodology
docs/testing/GREENHOUSE_VALIDATION.md    → Test documentation
docs/database/SCHEMA_UPDATES.md          → Schema migration docs
docs/architecture/DUAL_PIPELINE.md       → Architecture deep-dive
scrapers/greenhouse/README.md            → Greenhouse scraper docs
```

---

## 6. Execution Plan

### Phase 1: Create Archive Directories
```bash
mkdir -p docs/archive/tests
mkdir -p output/validation_history
mkdir -p output/test_outputs
```

### Phase 2: Move Test Files
```bash
# Move root-level test files to archive
mv test_classify_only.py docs/archive/tests/
mv test_dedupe_only.py docs/archive/tests/
mv test_greenhouse_only.py docs/archive/tests/
mv test_insert_greenhouse.py docs/archive/tests/
mv test_store_only.py docs/archive/tests/
mv test_unified_job_fix.py docs/archive/tests/
mv test_pipeline_integration.py docs/archive/tests/
mv test_database_insertion.py docs/archive/tests/
```

### Phase 3: Move JSON Outputs
```bash
# Move validation outputs
mv validation_metrics.json output/validation_history/
mv validation_metrics_debug.json output/validation_history/
mv validation_metrics_fast.json output/validation_history/
mv validation_metrics_adzuna_only.json output/validation_history/
mv validation_test.json output/validation_history/
mv validation_both_sources.json output/validation_history/

# Move test outputs
mv test_merged_jobs.json output/test_outputs/
mv test_classified_jobs.json output/test_outputs/
mv test_greenhouse_jobs.json output/test_outputs/
```

### Phase 4: Move Recent Fixes Doc
```bash
mv FIXES_APPLIED_2025-11-24.md docs/archive/
```

### Phase 5: Update Core Documentation
1. Update CLAUDE.md (Epic status)
2. Update docs/system_architecture.yaml (pipeline status)
3. Update docs/product_brief.yaml (timeline)
4. Review docs/README.md (ensure accurate)

---

## 7. Final Repository Structure

```
job-analytics/
├── CLAUDE.md                          ← Updated with current status
├── fetch_jobs.py                      ← Main pipeline
├── classifier.py                      ← LLM integration
├── unified_job_ingester.py            ← Merge logic
├── db_connection.py                   ← Database layer
├── agency_detection.py                ← Agency filtering
├── backfill_agency_flags.py           ← Maintenance
├── validate_pipeline.py               ← Epic 4 (to run)
│
├── config/
│   ├── agency_blacklist.yaml          ← Active config
│   ├── supported_ats.yaml             ← Active config
│   └── company_ats_mapping.json       ← Active config
│
├── docs/
│   ├── README.md                      ← Updated index
│   ├── system_architecture.yaml       ← Updated status
│   ├── schema_taxonomy.yaml           ← Active spec
│   ├── product_brief.yaml             ← Updated timeline
│   ├── marketplace_questions.yaml     ← Active spec
│   ├── blacklisting_process.md        ← Active doc
│   ├── DATABASE_SCHEMA_UPDATE.md      ← Schema docs
│   ├── architecture/
│   │   └── DUAL_PIPELINE.md
│   ├── database/
│   │   └── SCHEMA_UPDATES.md
│   ├── testing/
│   │   └── GREENHOUSE_VALIDATION.md
│   └── archive/                       ← Historical docs + old tests
│
├── scrapers/
│   ├── adzuna/
│   │   ├── fetch_adzuna_jobs.py       ← Active
│   │   └── sample_adzuna_jobs.csv
│   └── greenhouse/
│       ├── greenhouse_scraper.py      ← Active
│       └── README.md
│
├── tests/                             ← Active test suite only
│   ├── test_greenhouse_scraper_simple.py
│   ├── test_two_companies.py
│   ├── test_end_to_end.py
│   ├── test_ats_scraping.py
│   ├── test_orchestrator.py
│   └── test_failed_job.py
│
├── output/
│   ├── validation_history/            ← Old validation runs
│   ├── test_outputs/                  ← Old test outputs
│   └── [other generated files]
│
└── [Keep]
    ├── test_full_pipeline_scale.py    ← Useful for Epic 4
    ├── greenhouse_validation_results.json
    ├── greenhouse_validation_results.csv
    └── validation_metrics_full_pipeline.json
```

---

## 8. Success Criteria

**After cleanup:**
- ✅ Root directory has only active scripts + main docs
- ✅ All one-off test files archived
- ✅ Historical JSON outputs moved to output/
- ✅ Core documentation updated with current status
- ✅ Clear separation: active code vs. archived artifacts
- ✅ Easy to understand what's in production vs. testing

---

## 9. Next Steps After Cleanup

1. **Run Epic 4 validation:** `python validate_pipeline.py --cities lon,nyc --max-jobs 100`
2. **Review validation results:** Confirm unit economics and quality
3. **Proceed to Epic 5:** Build analytics.py query layer
4. **Streamlit dashboard:** Epic 6 implementation
