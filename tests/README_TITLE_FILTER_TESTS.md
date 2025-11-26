# Greenhouse Title Filter Test Suite - Usage Guide

## Overview

This test suite validates the greenhouse title filtering feature that reduces classification costs by 60-70% by filtering jobs BEFORE expensive LLM processing.

**Test Coverage:**
- **Unit Tests:** 18 tests - Pattern loading and matching logic
- **Integration Tests:** 9 tests - Scraper initialization and metrics
- **E2E Tests:** 12 tests - Full pipeline integration
- **Total:** 39 automated tests

---

## Quick Start

### Run All Fast Tests (Recommended for Development)

```bash
# Run all tests except live integration tests (~1 second)
python -m pytest tests/test_greenhouse_title_filter_unit.py tests/test_greenhouse_scraper_filtered.py tests/test_e2e_greenhouse_filtered.py -v -m "not integration"
```

### Run Specific Test Suites

```bash
# Unit tests only (pattern matching logic)
python -m pytest tests/test_greenhouse_title_filter_unit.py -v

# Integration tests only (scraper configuration)
python -m pytest tests/test_greenhouse_scraper_filtered.py -v -m "not integration"

# E2E tests only (pipeline integration)
python -m pytest tests/test_e2e_greenhouse_filtered.py -v

# Live integration tests (requires network, slower ~30-60 seconds)
python -m pytest tests/test_greenhouse_scraper_filtered.py -m integration -v
```

### Run Live Validation on Real Company

```bash
# Test on Monzo (validates filtering in production-like scenario)
python tests/test_monzo_filtering.py
```

---

## When to Run Tests

### 1. **Before Committing Code**
Run fast tests to ensure nothing broke:
```bash
pytest tests/test_greenhouse_title_filter_unit.py tests/test_greenhouse_scraper_filtered.py tests/test_e2e_greenhouse_filtered.py -v -m "not integration" -q
```

### 2. **After Updating Title Patterns**
When you edit `config/greenhouse_title_patterns.yaml`:

```bash
# Run pattern matching tests
pytest tests/test_greenhouse_title_filter_unit.py::TestIsRelevantRole -v
pytest tests/test_greenhouse_title_filter_unit.py::TestIntegrationWithRealPatterns -v

# Validate on real company
python tests/test_monzo_filtering.py
```

**What to check:**
- Unit tests still pass
- Real company test shows expected filter rate (70-90%)
- No Data/Product jobs filtered out (check `filtered_titles_sample`)

### 3. **After Modifying Scraper Code**
When you change `scrapers/greenhouse/greenhouse_scraper.py`:

```bash
# Run integration tests
pytest tests/test_greenhouse_scraper_filtered.py -v

# Run E2E tests
pytest tests/test_e2e_greenhouse_filtered.py -v
```

### 4. **Before Production Deployment**
Full validation before deploying:

```bash
# Run all tests including live integration
pytest tests/ -v

# Test on 2-3 real companies
python tests/test_monzo_filtering.py
# Manually test Stripe or another company
```

### 5. **Monthly Maintenance**
Regular health checks:

```bash
# Run full test suite
pytest tests/test_greenhouse_title_filter_unit.py tests/test_greenhouse_scraper_filtered.py tests/test_e2e_greenhouse_filtered.py -v

# Validate on production companies
python tests/test_monzo_filtering.py
```

---

## Maintaining the Test Suite

### Adding New Title Patterns

**Step 1:** Add pattern to `config/greenhouse_title_patterns.yaml`

```yaml
relevant_title_patterns:
  # New pattern
  - 'your new pattern here'
```

**Step 2:** Add test case to verify it works

Edit `tests/test_greenhouse_title_filter_unit.py`:

```python
def test_is_relevant_role_your_new_pattern(self):
    """Test your new pattern matching"""
    patterns = ['your new pattern']

    # Should match
    assert is_relevant_role('Example Title That Should Match', patterns) == True

    # Should NOT match
    assert is_relevant_role('Example Title That Should NOT Match', patterns) == False
```

**Step 3:** Run tests to validate

```bash
pytest tests/test_greenhouse_title_filter_unit.py::TestIsRelevantRole::test_is_relevant_role_your_new_pattern -v
```

**Step 4:** Validate on real data

```bash
python tests/test_monzo_filtering.py
# Check that jobs you expect to match are now kept
```

### Handling Test Failures

#### Unit Test Failure

```
FAILED test_is_relevant_role_data_scientist - AssertionError: assert False == True
```

**Cause:** Pattern doesn't match expected title
**Fix:** Update pattern in `config/greenhouse_title_patterns.yaml` or adjust test expectations

#### Integration Test Failure

```
FAILED test_filter_stats_accuracy - AssertionError: expected filter_rate 65.0 but got 70.0
```

**Cause:** Filter rate calculation mismatch
**Fix:** Check `greenhouse_scraper.py:329-337` for filter rate calculation logic

#### E2E Test Failure

```
FAILED test_end_to_end_flow_simulation - AssertionError: len(filtered_jobs) == 2 but expected 3
```

**Cause:** Pattern matching changed behavior
**Fix:** Update test expectations or verify patterns are correct

### Updating Test Data

**When Monzo's job listings change:**

Edit `test_monzo_filtering.py`:

```python
# Update expected ranges based on current Monzo job listings
if 70 <= stats['filter_rate'] <= 95:  # Adjust range if needed
    checks.append(("[PASS]", f"Filter rate {stats['filter_rate']}% within expected range"))
```

---

## Test Suite Architecture

### Test Layers

```
test_greenhouse_title_filter_unit.py (Unit Tests)
├── TestLoadTitlePatterns
│   ├── Pattern loading from YAML
│   ├── Error handling (missing files, malformed YAML)
│   └── Custom pattern paths
│
├── TestIsRelevantRole
│   ├── Data Scientist family
│   ├── ML Engineer family
│   ├── Data Engineer family
│   ├── Data Analyst family
│   ├── Product Manager family
│   ├── Seniority prefixes
│   ├── Negative cases (Sales, Marketing, etc.)
│   └── Edge cases
│
└── TestIntegrationWithRealPatterns
    ├── Validation with actual config
    └── Negative case validation

test_greenhouse_scraper_filtered.py (Integration Tests)
├── TestScraperInitialization
│   ├── With/without filtering
│   ├── Custom patterns
│   └── Stats reset
│
├── TestFilteringMetrics
│   ├── Stats calculations
│   ├── Cost savings formula
│   └── Filter rate calculations
│
├── TestFilteringLogic
│   └── Description fetch prevention
│
└── TestLiveScraperFiltering (@pytest.mark.integration)
    ├── Real company scraping
    ├── Filter rate validation
    └── Cost savings validation

test_e2e_greenhouse_filtered.py (E2E Tests)
├── TestE2EPipelineWithFiltering
│   ├── Pipeline output format
│   ├── Deduplication integration
│   ├── Agency filtering integration
│   ├── Stats structure
│   ├── Cost tracking
│   └── Multi-company aggregation
│
└── TestFilteringProductionReadiness
    ├── Empty list handling
    ├── 100% filter rate scenario
    ├── 0% filter rate scenario
    └── Memory limits
```

---

## Test Configuration

### Pytest Markers

Defined in `pytest.ini`:

```ini
markers =
    asyncio: marks tests as async
    integration: marks tests as integration tests (slower, requires network)
    slow: marks tests as slow running (>10 seconds)
    e2e: marks tests as end-to-end tests
```

**Usage:**

```bash
# Skip integration tests
pytest -m "not integration"

# Run only integration tests
pytest -m integration

# Run only slow tests
pytest -m slow

# Skip both integration and slow tests
pytest -m "not integration and not slow"
```

---

## Continuous Integration (Future)

### GitHub Actions Example

```yaml
name: Title Filter Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run fast tests
        run: |
          pytest tests/test_greenhouse_title_filter_unit.py tests/test_greenhouse_scraper_filtered.py tests/test_e2e_greenhouse_filtered.py -v -m "not integration"

      - name: Run integration tests (weekly)
        if: github.event.schedule == '0 0 * * 0'  # Sundays only
        run: |
          pytest tests/test_greenhouse_scraper_filtered.py -m integration -v
```

---

## Troubleshooting

### Tests Pass Locally But Fail in CI

**Cause:** Network issues, browser automation failures
**Fix:** Use `-m "not integration"` in CI to skip live tests

### Pattern Test Fails After Config Update

**Cause:** Pattern syntax error or pattern too broad
**Fix:** Test pattern manually:

```python
from scrapers.greenhouse.greenhouse_scraper import is_relevant_role
patterns = ['your pattern']
print(is_relevant_role('Test Title', patterns))
```

### Monzo Test Shows Different Filter Rate

**Cause:** Monzo changed their job listings
**Fix:** This is expected - update validation ranges in `test_monzo_filtering.py`

### Import Errors

**Cause:** Missing dependencies
**Fix:**

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio
```

---

## Best Practices

### 1. **Run Fast Tests Frequently**
```bash
# Add to your workflow (runs in ~1 second)
pytest tests/test_greenhouse_title_filter_unit.py -q
```

### 2. **Run Live Tests Before Deployment**
```bash
# Weekly or before major releases
python tests/test_monzo_filtering.py
```

### 3. **Keep Tests Updated**
- Update expected values when patterns change
- Add new test cases for new patterns
- Remove obsolete tests

### 4. **Monitor Production**
After deploying pattern changes:
- Check `filtered_titles_sample` for false negatives
- Verify filter rate is in expected range (70-90%)
- Track cost savings

### 5. **Document Pattern Changes**
When updating patterns:
```yaml
# config/greenhouse_title_patterns.yaml
relevant_title_patterns:
  # Added 2025-12-01: Cover "Data Architect" roles
  - 'data architect'
```

---

## Related Files

**Test Files:**
- `tests/test_greenhouse_title_filter_unit.py` - Unit tests
- `tests/test_greenhouse_scraper_filtered.py` - Integration tests
- `tests/test_e2e_greenhouse_filtered.py` - E2E tests
- `test_monzo_filtering.py` - Live validation script

**Configuration:**
- `config/greenhouse_title_patterns.yaml` - Title patterns
- `pytest.ini` - Pytest configuration

**Implementation:**
- `scrapers/greenhouse/greenhouse_scraper.py` - Filtering logic (lines 41-101, 367-427)

**Documentation:**
- `docs/testing/greenhouse_title_filter_implementation.md` - Full implementation details
- `docs/testing/greenhouse_title_filter_next_steps.md` - Development roadmap

---

## Quick Reference

**Common Commands:**

```bash
# Development (fast)
pytest tests/test_greenhouse_title_filter_unit.py -q

# Pre-commit (comprehensive, fast)
pytest tests/ -m "not integration" -v

# Pre-deploy (full validation)
pytest tests/ -v && python tests/test_monzo_filtering.py

# After pattern update
pytest tests/test_greenhouse_title_filter_unit.py::TestIntegrationWithRealPatterns -v

# Debug specific test
pytest tests/test_greenhouse_title_filter_unit.py::TestIsRelevantRole::test_is_relevant_role_data_scientist -v -s
```

**Test Selection:**

```bash
# By file
pytest tests/test_greenhouse_title_filter_unit.py

# By class
pytest tests/test_greenhouse_title_filter_unit.py::TestIsRelevantRole

# By function
pytest tests/test_greenhouse_title_filter_unit.py::TestIsRelevantRole::test_is_relevant_role_data_scientist

# By marker
pytest -m integration
pytest -m "not integration"
```

---

## Success Metrics

**Test suite is healthy when:**
- ✅ All 39 fast tests pass in <2 seconds
- ✅ Integration tests pass with filter rate 70-90%
- ✅ No Data/Product jobs in `filtered_titles_sample`
- ✅ Cost savings estimates match live results
- ✅ Tests run without warnings

**Red flags:**
- ❌ Filter rate drops below 50% (patterns too restrictive)
- ❌ Filter rate above 95% (patterns too broad, may filter relevant jobs)
- ❌ Data/Product jobs appear in `filtered_titles_sample`
- ❌ Test failures after pattern updates
- ❌ Integration tests timing out

---

## Getting Help

**Test failures:**
1. Read the error message carefully
2. Check if patterns changed recently
3. Validate patterns manually with `is_relevant_role()`
4. Check implementation docs in `docs/testing/`

**Pattern questions:**
- See `config/greenhouse_title_patterns.yaml` comments
- Check validation notes in config file
- Review `docs/testing/greenhouse_title_filter_implementation.md`

**Integration issues:**
- Check network connectivity
- Verify Playwright browser installed: `playwright install chromium`
- Check company still uses Greenhouse ATS
