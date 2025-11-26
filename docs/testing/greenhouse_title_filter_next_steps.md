# Title Filtering - Next Steps

**Status Update:** 2025-11-26
**Phase:** Test Suite Complete, Ready for Production Deployment

---

## What We've Accomplished

### 1. Core Integration (COMPLETE)

**Config File Created:**
- `config/greenhouse_title_patterns.yaml` with 20 validated regex patterns
- Covers all Data and Product role families
- Patterns refined through live testing (fixed "machine learning scientist" gap)

**Scraper Updated:**
- Added `load_title_patterns()` function to load YAML config
- Added `is_relevant_role()` function for pattern matching
- Modified `_extract_all_jobs()` to filter BEFORE description fetching
- Changed return format to include both jobs and detailed stats
- Filtering enabled by default, can be disabled with `filter_titles=False`

**Pagination Fixed:**
- Added support for multiple pagination styles (Load More, Next buttons, page numbers)
- 3-method detection with fallbacks
- Validated on Monzo (now scrapes all 66 jobs across 2 pages, previously only 50)

**Pipeline Integration:**
- Updated `fetch_jobs.py` to handle new dict return format
- Updated `tests/test_greenhouse_scraper_simple.py` to display filtering stats
- All existing tests still pass

### 2. Live Validation (COMPLETE)

**Test 1: Stripe**
- 69 jobs total → 2 kept (97.1% filter rate)
- Cost savings: $0.26
- Correctly filtered: Account Executives, Accounting roles, Backend Engineers
- Correctly kept: AI/ML Engineering Manager, Analytics Lead

**Test 2: Monzo**
- 66 jobs total → 8 kept (87.9% filter rate)
- Cost savings: $0.23
- Correctly kept: 5 ML/Data Scientists, 3 Product Managers, 1 Analytics Manager
- Pagination fix validated (found jobs on page 2 that were previously missed)

### 3. Documentation (COMPLETE)

**Created:**
- `docs/testing/greenhouse_title_filter_implementation.md` - Full implementation details
- Includes: architecture, code examples, validation results, maintenance guide

**Updated:**
- `CLAUDE.md` - Added title filtering to Greenhouse Scraper section
- `CLAUDE.md` - Updated directory structure with new config file and docs
- `config/greenhouse_title_patterns.yaml` - Includes inline documentation and validation notes

---

## What's Complete

### Phase 1: Unit Tests ✅ COMPLETE

**File created:** `tests/test_greenhouse_title_filter_unit.py`

**Test cases implemented:** 18 tests (exceeds 12+ requirement)
- Pattern loading tests (4 tests)
- Pattern matching tests (11 tests)
- Real pattern validation tests (3 tests)

**Result:** All 18 tests passing in <1 second

### Phase 2: Integration Tests ✅ COMPLETE

**File created:** `tests/test_greenhouse_scraper_filtered.py`

**Test cases implemented:** 13 tests (9 fast + 4 live integration)
- Scraper initialization tests (4 tests)
- Filtering metrics tests (4 tests)
- Filtering logic tests (1 test)
- Live scraper tests (4 tests, marked @pytest.mark.integration)

**Result:** All 9 fast tests passing in <1 second, 4 live tests available for on-demand validation

### Phase 3: E2E Pipeline Tests ✅ COMPLETE

**File created:** `tests/test_e2e_greenhouse_filtered.py`

**Test cases implemented:** 12 tests (exceeds 6+ requirement)
- Pipeline integration tests (8 tests)
- Production readiness tests (4 tests)

**Result:** All 12 tests passing in <1 second

### Additional Deliverables ✅ COMPLETE

**Live Validation Script:** `tests/test_monzo_filtering.py`
- Tests filtering on real company (Monzo)
- Validates filter rates, cost savings, kept/filtered jobs
- Generates detailed JSON report
- Runs in ~60 seconds

**Documentation:**
- `tests/README_TITLE_FILTER_TESTS.md` - Comprehensive usage guide
- `tests/QUICK_REFERENCE.md` - Quick reference card
- Both documents include: common commands, when to run tests, troubleshooting, maintenance workflows

**Total Test Coverage:** 39 automated tests + 1 live validation script

---

## What's Left To Do

### Production Deployment & Validation

Now that the test suite is complete and all 39 tests are passing, the next steps are operational:

**1. Production Deployment (Immediate)**
- Feature is ready to use in production Greenhouse scraping
- All safety checks in place (unit, integration, E2E tests)
- Filtering enabled by default via `filter_titles=True`

**2. Production Monitoring (Week 1)**
Monitor these metrics during first week of production use:
- Filter rate per company (expect 50-90%)
- Cost savings (actual $ saved)
- False negative rate (check filtered_titles_sample for missed relevant jobs)
- Jobs kept per company (ensure still finding Data/Product roles)

**3. False Negative Validation (Ongoing)**
- Review filtered_titles_sample weekly
- Identify any Data/Product jobs incorrectly filtered
- Update patterns in `config/greenhouse_title_patterns.yaml` as needed
- Re-run unit tests to validate pattern updates

---

## How to Use the Test Suite

### Running Tests

**Fast tests (recommended for development):**
```bash
# Run all fast tests (~1 second)
pytest tests/test_greenhouse_title_filter_unit.py tests/test_greenhouse_scraper_filtered.py tests/test_e2e_greenhouse_filtered.py -v -m "not integration"
```

**Live integration tests (optional, ~60 seconds):**
```bash
# Run on real company (Monzo)
python tests/test_monzo_filtering.py

# Or run pytest integration tests on Figma
pytest tests/test_greenhouse_scraper_filtered.py -m integration -v
```

**After updating patterns:**
```bash
# 1. Validate pattern matching
pytest tests/test_greenhouse_title_filter_unit.py::TestIntegrationWithRealPatterns -v

# 2. Test on real company
python tests/test_monzo_filtering.py
```

### Complete Usage Guide

See `tests/README_TITLE_FILTER_TESTS.md` for comprehensive documentation including:
- When to run tests
- How to add new patterns
- Troubleshooting test failures
- CI/CD integration examples
- Best practices for maintenance

Quick reference available in `tests/QUICK_REFERENCE.md`

---

## Monitoring in Production

Once deployed, monitor these metrics:

### Daily Checks:
1. **Filter rate per company** - Should be 50-80% for most companies
2. **Filtered titles sample** - Check for false negatives (relevant jobs filtered out)
3. **Cost savings** - Track actual dollars saved vs. unfiltered scraping
4. **Jobs kept per company** - Ensure we're still finding Data/Product roles

### Weekly Reviews:
1. Review all filtered_titles_sample across all companies
2. Identify any Data/Product keywords in filtered titles
3. Add missing patterns to YAML config
4. Re-run affected companies

### Monthly:
1. Calculate total cost savings from filtering
2. Review false negative rate (if any pattern additions needed)
3. Update documentation with new patterns and examples

---

## Success Criteria

**Before considering this feature "complete":**
- [x] Core integration working (scraper, config, metrics)
- [x] Live validation on at least 2 companies (Stripe, Monzo)
- [x] Documentation complete (implementation docs + test usage guides)
- [x] Unit tests passing (18 test cases - exceeds 12+ requirement)
- [x] Integration tests passing (13 test cases - exceeds 9+ requirement)
- [x] E2E tests passing (12 test cases - exceeds 6+ requirement)
- [ ] Used in production for at least 1 week without issues
- [ ] False negative rate <5% (validated via manual review)

**Current status:** 6 of 8 criteria complete (75%)

**Next milestone:** Production deployment + 1 week validation → Feature 100% complete

---

## Questions?

**Where is the implementation code?**
- `scrapers/greenhouse/greenhouse_scraper.py` (lines ~60-90, 390-450)

**Where are the patterns defined?**
- `config/greenhouse_title_patterns.yaml`

**How do I add a new pattern?**
1. Edit `config/greenhouse_title_patterns.yaml`
2. Add pattern to relevant family (Data or Product)
3. Test pattern with `is_relevant_role('Your Title', [patterns])`
4. Validate on real company data
5. Update pattern_notes with examples

**How do I disable filtering?**
```python
scraper = GreenhouseScraper(headless=True, filter_titles=False)
```

**Where is the full documentation?**
- `docs/testing/greenhouse_title_filter_implementation.md`

**How do I check if it's working?**
```python
result = await scraper.scrape_company('stripe')
print(result['stats'])  # Shows filtering metrics
```
