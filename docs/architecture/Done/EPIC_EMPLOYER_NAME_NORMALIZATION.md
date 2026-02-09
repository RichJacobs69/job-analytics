# Epic: Employer Name Normalization

## Status: Phases 1-2 Complete (2026-02-09)

## Problem

Different data sources produce different employer name variants for the same company. The current normalization logic in `db_connection.py` only applies `.lower().strip()`, which preserves internal spaces and formatting differences. This creates duplicate employer entries in `enriched_jobs` that surface as separate employers in reports.

### Example: Rightmove

- **Greenhouse** stores the ATS slug: `rightmovecareers` (no space)
- **Adzuna** stores the API display name: `Rightmove Careers` (with space)
- After normalization: `rightmovecareers` vs `rightmove careers` -- two distinct values
- Result: appeared as two separate employers in report charts

### Example: JPMorgan Chase (NYC reports)

Three separate employer_name values across sources:
- `jpmorgan chase bank, n.a.` (Adzuna legal entity name)
- `jpmorgan chase` (Adzuna display name)
- `jpmorganchase` (Greenhouse slug)
- Result: appeared as three separate employers in NYC reports

## What Was Done

### Phase 1: Fix display names [DONE 2026-02-09]

**Bug 1: `ensure_employer_metadata()` was create-only.** When the pipeline processes a job, it passes `display_name_hint` (from ATS config) to `insert_enriched_job()`, which calls `ensure_employer_metadata()`. But if the row already existed, the function returned immediately without updating `display_name`. Fixed to conditionally update when the current display_name equals the lowercase canonical (clearly never set properly).

**Bug 2: `load_display_names_from_config()` keyed by slug only.** For non-Greenhouse sources, the DB `canonical_name` is `display_name.lower()`, not the slug. Added dual-key lookup (slug + display_name.lower()) for Lever, Ashby, Workable, SmartRecruiters. Also added missing Workable config loading.

**Smart title-case fallback for Adzuna-only employers.** Added `smart_title_case()` in `backfill_display_names.py` that handles acronyms (HP, AWS, GSK), ordinals (1st, 22nd), and short brand names (Box, Sky, Arm). Single-word 2-3 char names default to uppercase unless in an exception list. Applied to ~6,900 Adzuna-only employers.

**Report generator now uses employer_metadata.** Replaced `.title()` workarounds with `_get_display_name()` that looks up proper casing from the employer_metadata cache. Display names resolved at source in `_calculate_employer_metrics()`.

**Files changed:**
- `pipeline/db_connection.py` -- `ensure_employer_metadata()` conditionally updates display_name
- `pipeline/utilities/seed_employer_metadata.py` -- dual-key config lookup, Workable support
- `pipeline/utilities/backfill_display_names.py` -- new backfill script with smart title-case
- `pipeline/report_generator.py` -- `_get_display_name()`, removed `.title()` workarounds

### Phase 2: Merge duplicate employers in reports [DONE 2026-02-09]

Added `EMPLOYER_MERGE_MAP` to `report_generator.py` that consolidates employers appearing under multiple canonical names. Merging happens at the count stage so concentration metrics are also correct.

**Current merge map:**
- JPMorgan Chase Bank, N.A. + JPMorganChase -> JPMorgan Chase
- Rightmove Careers + RightmoveCareers -> Rightmove
- NBC Universal -> NBCUniversal
- Cbre Enterprise Emea -> CBRE
- Sierra Nevada Company, LLC -> Sierra Nevada Corporation
- Tradeweb Markets -> Tradeweb

**File:** `pipeline/report_generator.py` -- `EMPLOYER_MERGE_MAP` + `_merge_employer_counts()`

### Phase 3: Improve ingestion normalization [NOT STARTED]

- Enhance `db_connection.py` normalization to strip common suffixes (e.g., "careers", "jobs", "hiring")
- Remove spaces/hyphens for comparison
- Risk: must avoid false merges

### Phase 4: Audit and backfill [NOT STARTED]

- Run a one-time audit across all `enriched_jobs` employer names to identify duplicates
- Backfill `employer_metadata` with canonical mappings for confirmed duplicates

## Files Involved

| File | Role |
|------|------|
| `pipeline/db_connection.py` | Normalization logic, `ensure_employer_metadata()` |
| `pipeline/report_generator.py` | `_get_display_name()`, `EMPLOYER_MERGE_MAP` |
| `pipeline/utilities/seed_employer_metadata.py` | Seeds employer_metadata from config (dual-key) |
| `pipeline/utilities/backfill_display_names.py` | One-time backfill with smart title-case |
| `config/greenhouse/company_ats_mapping.json` | Greenhouse slug -> display name |
| `config/lever/company_mapping.json` | Lever slug -> display name |
| `config/ashby/company_mapping.json` | Ashby slug -> display name |
| `config/workable/company_mapping.json` | Workable slug -> display name |
| `config/smartrecruiters/company_mapping.json` | SmartRecruiters slug -> display name |

## Risk

- False merges: `EMPLOYER_MERGE_MAP` is manually curated to avoid this
- Phase 3 (ingestion normalization) carries higher risk and needs careful testing
