# Job Analytics Testing Guide

## Quick Reference

### Most Common Commands

```bash
# Daily development - run all fast tests (~1 second)
pytest tests/ -v -m "not integration"

# After updating title patterns
pytest tests/test_greenhouse_title_filter_unit.py::TestIntegrationWithRealPatterns -v
python tests/test_monzo_filtering.py

# Before deployment - full validation
pytest tests/ -v
python tests/test_monzo_filtering.py

# Run specific test suites
pytest tests/test_greenhouse_title_filter_unit.py -v          # Unit tests only
pytest tests/test_greenhouse_scraper_filtered.py -v           # Integration tests
pytest tests/test_e2e_greenhouse_filtered.py -v               # E2E tests
pytest tests/test_incremental_pipeline.py -v                  # Incremental pipeline tests
```

---

## Test Suite Overview

### Title Filter Tests (Greenhouse)

Validates the title filtering feature that reduces classification costs by 60-70% by filtering jobs BEFORE expensive LLM processing.

**Test Coverage:**
- **Unit Tests:** 18 tests - Pattern loading and matching logic
- **Integration Tests:** 9 tests - Scraper initialization and metrics
- **E2E Tests:** 12 tests - Full pipeline integration
- **Total:** 39 automated tests

**Key Files:**
- `test_greenhouse_title_filter_unit.py` - Pattern matching logic (<1s)
- `test_greenhouse_scraper_filtered.py` - Scraper integration (<1s)
- `test_e2e_greenhouse_filtered.py` - Full pipeline (<1s)
- `test_monzo_filtering.py` - Live validation (~60s)

### Pipeline Tests

- `test_incremental_pipeline.py` - Incremental upsert feature validation
- `test_db_upsert.py` - Database upsert logic
- `test_resume_capability.py` - Resume capability tests
- `test_end_to_end.py` - Full pipeline integration

### Scraper Tests

- `test_greenhouse_scraper_simple.py` - Basic scraper functionality
- `test_figma_location_filter.py` - Location filtering validation
- `test_two_companies.py` - Multi-company scraping

---

## When to Run Tests

### 1. Before Committing Code
Run fast tests to ensure nothing broke:
```bash
pytest tests/ -m "not integration" -q
```

### 2. After Updating Title Patterns
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

### 3. After Modifying Scraper Code
When you change `scrapers/greenhouse/greenhouse_scraper.py`:

```bash
# Run integration tests
pytest tests/test_greenhouse_scraper_filtered.py -v

# Run E2E tests
pytest tests/test_e2e_greenhouse_filtered.py -v
```

### 4. After Database Schema Changes
When you modify database schema or connection logic:

```bash
pytest tests/test_db_upsert.py -v
pytest tests/test_incremental_pipeline.py -v
```

### 5. Before Production Deployment
Full validation before deploying:

```bash
# Run all tests including live integration
pytest tests/ -v

# Test on 2-3 real companies
python tests/test_monzo_filtering.py
```

### 6. Monthly Maintenance
Regular health checks:

```bash
# Run full test suite
pytest tests/ -v

# Validate on production companies
python tests/test_monzo_filtering.py
```

---

## Expected Test Results

### Fast Tests (< 2 seconds)
- ✅ All 39 title filter tests should pass
- ✅ All pipeline unit tests should pass
- ✅ Run time: <1 second each file

### Live Integration Tests (Monzo)
- **Jobs scraped:** ~60-70
- **Jobs kept:** ~8-12 (Data/Product roles)
- **Filter rate:** 75-90%
- **Cost savings:** ~$0.20-$0.25

### Success Indicators

✅ **Healthy:**
- All tests passing
- Filter rate 70-90%
- No Data/Product jobs in filtered_titles_sample
- Cost savings ~$0.20-$0.25 per company

❌ **Needs Attention:**
- Filter rate <50% or >95%
- Data Scientist/ML/Product jobs being filtered
- Test failures after pattern updates

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

# Skip both integration and slow tests
pytest -m "not integration and not slow"
```

---

## Maintaining Tests

### Adding New Title Patterns

**Step 1:** Add pattern to `config/greenhouse_title_patterns.yaml`

```yaml
relevant_title_patterns:
  # Added 2025-12-07: Cover "Data Architect" roles
  - 'data architect'
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

---

## Troubleshooting

### Common Issues

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

#### Monzo Test Shows Different Numbers
**Expected:** Job listings change frequently  
**Fix:** Update validation ranges in `test_monzo_filtering.py` if filter rate changed significantly

#### Import Error
**Fix:**
```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio
```

### Quick Debugging

```bash
# Test specific pattern
pytest tests/test_greenhouse_title_filter_unit.py::TestIsRelevantRole::test_is_relevant_role_data_scientist -v -s

# See full output
pytest tests/test_greenhouse_title_filter_unit.py -v -s

# Run with debugger
pytest tests/test_greenhouse_title_filter_unit.py --pdb
```

### Pattern Testing Workflow

1. **Edit** `config/greenhouse_title_patterns.yaml`
2. **Test** patterns:
   ```bash
   pytest tests/test_greenhouse_title_filter_unit.py::TestIntegrationWithRealPatterns -v
   ```
3. **Validate** on real data:
   ```bash
   python tests/test_monzo_filtering.py
   ```
4. **Check** filtered_titles_sample for false negatives
5. **Commit** if all checks pass

---

## Test Architecture

### Test Layers

```
Unit Tests (test_greenhouse_title_filter_unit.py)
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

Integration Tests (test_greenhouse_scraper_filtered.py)
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
└── TestLiveScraperFiltering (@pytest.mark.integration)
    ├── Real company scraping
    ├── Filter rate validation
    └── Cost savings validation

E2E Tests (test_e2e_greenhouse_filtered.py)
├── TestE2EPipelineWithFiltering
│   ├── Pipeline output format
│   ├── Deduplication integration
│   ├── Agency filtering integration
│   ├── Stats structure
│   └── Cost tracking
│
└── TestFilteringProductionReadiness
    ├── Empty list handling
    ├── 100% filter rate scenario
    ├── 0% filter rate scenario
    └── Memory limits

Pipeline Tests
├── test_incremental_pipeline.py - Incremental upsert validation
├── test_db_upsert.py - Database upsert logic
├── test_resume_capability.py - Resume capability
└── test_end_to_end.py - Full pipeline integration
```

---

## Best Practices

### 1. Run Fast Tests Frequently
```bash
# Add to your workflow (runs in ~1 second)
pytest tests/ -m "not integration" -q
```

### 2. Run Live Tests Before Deployment
```bash
# Weekly or before major releases
python tests/test_monzo_filtering.py
```

### 3. Keep Tests Updated
- Update expected values when patterns change
- Add new test cases for new patterns
- Remove obsolete tests

### 4. Monitor Production
After deploying pattern changes:
- Check `filtered_titles_sample` for false negatives
- Verify filter rate is in expected range (70-90%)
- Track cost savings

### 5. Document Pattern Changes
When updating patterns:
```yaml
# config/greenhouse_title_patterns.yaml
relevant_title_patterns:
  # Added 2025-12-07: Cover "Data Architect" roles
  - 'data architect'
```

---

## Related Documentation

**Configuration:**
- `config/greenhouse_title_patterns.yaml` - Title patterns
- `config/greenhouse_location_patterns.yaml` - Location patterns
- `pytest.ini` - Pytest configuration

**Implementation:**
- `scrapers/greenhouse/greenhouse_scraper.py` - Filtering logic
- `pipeline/classifier.py` - LLM classification
- `pipeline/db_connection.py` - Database operations

**Documentation:**
- `CLAUDE.md` - Project overview and architecture
- `docs/README.md` - Documentation index
- `docs/REPOSITORY_STRUCTURE.md` - Repository organization

---

## Test Selection Reference

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

# Verbose output
pytest tests/ -v

# Quiet output
pytest tests/ -q

# Stop on first failure
pytest tests/ -x
```

---

## Getting Help

**Test failures:**
1. Read the error message carefully
2. Check if patterns changed recently
3. Validate patterns manually with `is_relevant_role()`
4. Review test architecture section above

**Pattern questions:**
- See `config/greenhouse_title_patterns.yaml` comments
- Check validation notes in config file
- Review pattern testing workflow above

**Integration issues:**
- Check network connectivity
- Verify Playwright browser installed: `playwright install chromium`
- Check company still uses Greenhouse ATS
- Review CLAUDE.md for pipeline architecture


