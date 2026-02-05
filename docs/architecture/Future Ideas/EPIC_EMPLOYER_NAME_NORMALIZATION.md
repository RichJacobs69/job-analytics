# Epic: Employer Name Normalization

## Status: Proposed

## Problem

Different data sources produce different employer name variants for the same company. The current normalization logic in `db_connection.py` only applies `.lower().strip()`, which preserves internal spaces and formatting differences. This creates duplicate employer entries in `enriched_jobs` that surface as separate employers in reports.

### Example: Rightmove

- **Greenhouse** stores the ATS slug: `rightmovecareers` (no space)
- **Adzuna** stores the API display name: `Rightmove Careers` (with space)
- After normalization: `rightmovecareers` vs `rightmove careers` -- two distinct values
- `report_generator.py` applies `.title()`: `Rightmovecareers` vs `Rightmove Careers`
- Result: appears as two separate employers in the report chart

### Example: JPMorgan Chase (NYC reports)

Three separate employer_name values across sources:
- `jpmorgan chase bank, n.a.` (Adzuna legal entity name)
- `jpmorgan chase` (Adzuna display name)
- `jpmorganchase` (Greenhouse slug)
- `report_generator.py` applies `.title()`: `Jpmorgan Chase Bank, N.A.`, `Jpmorgan Chase`, `Jpmorganchase`
- Result: appears as three separate employers in NYC reports (combined ~4-5%)

### Example: Display name casing from `.title()`

`.title()` fails on acronyms and brand-specific casing:
- `Ey` instead of `EY`
- `Pwc` instead of `PwC`
- `Sofi` instead of `SoFi`
- `Ntt Data` instead of `NTT Data`
- `Nbc Universal` / `Nbcuniversal` instead of `NBCUniversal`
- `Octoenergy` instead of `Octopus Energy`
- `Scale Ai` instead of `Scale AI`

These were manually fixed in report JSONs but will recur on every new report generation until Phase 1 is implemented.

### Scope

This likely affects other employers where:
- The Greenhouse/Workable slug differs from the Adzuna display name
- Historical data was ingested with inconsistent naming
- Companies with multi-word names have slug variants (e.g., `capitalonebank` vs `Capital One`)
- Legal entity names differ from brand names (e.g., `jpmorgan chase bank, n.a.` vs `JPMorgan Chase`)

## Current Architecture

1. **Ingestion** (`fetch_jobs.py`): Each source provides employer names in its own format
2. **Storage** (`db_connection.py`): `employer_name` normalized with `.lower().strip()` only
3. **Metadata** (`employer_metadata` table): Has `canonical_name` (lowercase key) and `display_name` (proper display)
4. **Reporting** (`report_generator.py`): Groups by `employer_name`, applies `.title()` for display -- does NOT use `employer_metadata.display_name`

## Proposed Fix

### Phase 1: Make report_generator use employer_metadata

- Change `report_generator.py` to look up `display_name` from `employer_metadata` instead of applying `.title()` to raw `employer_name`
- This immediately fixes display for any employer with metadata
- Falls back to `.title()` for employers without metadata entries

### Phase 2: Add canonical alias mapping

- Add an `aliases` table or column in `employer_metadata` that maps variant names to a canonical entry
- Example: `rightmovecareers` -> canonical `rightmove`, `rightmove careers` -> canonical `rightmove`
- The report_generator groups by canonical name instead of raw employer_name

### Phase 3: Improve ingestion normalization

- Enhance `db_connection.py` normalization to strip common suffixes (e.g., "careers", "jobs", "hiring")
- Remove spaces/hyphens for comparison: `rightmovecareers` and `rightmove careers` would match
- Risk: must avoid false merges (e.g., "AT&T" vs "ATT", distinct companies with similar names)

### Phase 4: Audit and backfill

- Run a one-time audit across all `enriched_jobs` employer names to identify duplicates
- SQL to find candidates: employers whose stripped names (no spaces/hyphens) match
- Backfill `employer_metadata` with canonical mappings for confirmed duplicates

## Files Involved

| File | Role |
|------|------|
| `pipeline/db_connection.py` | Normalization logic (`.lower().strip()`) |
| `pipeline/report_generator.py` | Display formatting (`.title()`) |
| `pipeline/utilities/seed_employer_metadata.py` | Seeds employer_metadata from config |
| `config/greenhouse/company_ats_mapping.json` | Greenhouse slug -> display name |
| `config/lever/company_mapping.json` | Lever slug -> display name |

## Risk

- False merges: Different companies with similar names could be incorrectly consolidated
- Data integrity: Changing employer_name in enriched_jobs requires careful migration
- Phase 1 (report_generator change) is low-risk and can be done independently
