# Title Filter Tests - Quick Reference Card

## Most Common Commands

### Daily Development
```bash
# Run all fast tests (~1 second)
pytest tests/test_greenhouse_title_filter_unit.py tests/test_greenhouse_scraper_filtered.py tests/test_e2e_greenhouse_filtered.py -v -m "not integration"
```

### After Updating Patterns
```bash
# 1. Run pattern tests
pytest tests/test_greenhouse_title_filter_unit.py::TestIntegrationWithRealPatterns -v

# 2. Test on real company
python tests/test_monzo_filtering.py
```

### Before Deployment
```bash
# Full test suite
pytest tests/ -v

# Live validation
python tests/test_monzo_filtering.py
```

## Test Files

| File | Purpose | Speed | When to Run |
|------|---------|-------|-------------|
| `test_greenhouse_title_filter_unit.py` | Pattern matching logic | <1s | After pattern changes |
| `test_greenhouse_scraper_filtered.py` | Scraper integration | <1s | After scraper code changes |
| `test_e2e_greenhouse_filtered.py` | Full pipeline | <1s | Before deployment |
| `test_monzo_filtering.py` | Live validation | ~60s | Weekly, before releases |

## Test Coverage Summary

✅ **39 automated tests**
- 18 unit tests (pattern matching)
- 9 integration tests (scraper config)
- 12 E2E tests (pipeline integration)
- 4 live integration tests (optional)

## Expected Results

### Unit Tests
- All 18 should pass
- Run in <1 second

### Integration Tests (Fast)
- All 9 should pass
- Run in <1 second

### E2E Tests
- All 12 should pass
- Run in <1 second

### Live Tests (Monzo)
- **Jobs scraped:** ~60-70
- **Jobs kept:** ~8-12 (Data/Product roles)
- **Filter rate:** 75-90%
- **Cost savings:** ~$0.20-$0.25

## Common Issues

### Test Fails After Pattern Update
**Fix:** Validate pattern syntax:
```python
from scrapers.greenhouse.greenhouse_scraper import is_relevant_role
patterns = ['your pattern']
is_relevant_role('Test Title', patterns)  # Should return True/False
```

### Monzo Test Shows Different Numbers
**Expected:** Job listings change frequently
**Fix:** Not needed unless filter rate drops dramatically

### Import Error
**Fix:**
```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio
```

## Success Indicators

✅ **Healthy:**
- All 39 tests passing
- Filter rate 70-90%
- No Data/Product jobs in filtered_titles_sample
- Cost savings ~$0.20-$0.25 per company

❌ **Needs Attention:**
- Filter rate <50% or >95%
- Data Scientist/ML/Product jobs being filtered
- Test failures after pattern updates

## Pattern Testing Workflow

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

## Quick Debugging

```bash
# Test specific pattern
pytest tests/test_greenhouse_title_filter_unit.py::TestIsRelevantRole::test_is_relevant_role_data_scientist -v -s

# See full output
pytest tests/test_greenhouse_title_filter_unit.py -v -s

# Run with debugging
pytest tests/test_greenhouse_title_filter_unit.py --pdb
```

## For Full Documentation

See `tests/README_TITLE_FILTER_TESTS.md` for complete usage guide.
