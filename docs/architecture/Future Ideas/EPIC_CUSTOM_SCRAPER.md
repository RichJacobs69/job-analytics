# EPIC: Custom Config Scraper Integration

**Status:** Phase 1 [COMPLETE] | Phases 2-4 [FUTURE]
**Started:** 2026-01-08
**Phase 1 Completed:** 2026-01-08
**Source Name:** `custom`

## Problem Statement

Large enterprises like Microsoft, Amazon, Apple, and Google use proprietary ATS platforms (Phenom, Taleo, custom) that cannot be scraped with our existing Greenhouse/Lever/Ashby/Workable scrapers. This limits our coverage of Fortune 500 companies.

**Current gap**: ~45% of Fortune 500 (Workday/Taleo/custom users) are not in our dataset.

---

## Decisions Made

| Decision | Choice |
|----------|--------|
| **Approach** | Build custom Playwright scrapers (not marketplace APIs) |
| **Strategy** | Supplement existing scrapers (keep Greenhouse/Lever/Ashby/Workable) |
| **Target employers** | Fortune 500 with focus on FAANG + Finance |
| **Refresh frequency** | Monthly (jobs typically turn over in 30-60 days) |
| **Technology** | Playwright for JS-heavy SPAs, config-driven selectors |

---

## Research Summary

### Enterprise ATS Platforms (Researched)

| Company | Platform | Careers URL | Difficulty |
|---------|----------|-------------|------------|
| **Google** | Custom | careers.google.com | **Easy** (has RSS feed!) |
| **Microsoft** | Phenom + iCIMS | careers.microsoft.com | Medium (JS SPA) |
| **Amazon** | Custom | amazon.jobs | Hard (heavy JS) |
| **Apple** | Custom (React) | jobs.apple.com | Medium |
| **Meta** | Custom (React SPA) | metacareers.com | Hard (SPA) |
| **Netflix** | Custom | explore.jobs.netflix.net | Medium |
| **JPMorgan** | Taleo (Oracle) | careers.jpmorgan.com | Medium (Taleo template) |
| **Goldman Sachs** | Taleo | goldmansachs.tal.net | Medium (Taleo template) |

### Key Findings

1. **Google has RSS** - Free, unlimited, no scraping needed
2. **Finance uses Taleo** - Can create shared Taleo selector template
3. **Microsoft uses Phenom** - May have reusable Phenom patterns
4. **FAANG mostly custom** - Each needs individual scraper config
5. **All are JS SPAs** - Playwright required (not simple HTTP requests)

### RSS Feed Availability

| Employer | RSS Available | Notes |
|----------|---------------|-------|
| **Google** | **YES** | Full catalog at `careers.google.com/jobs/feed.xml` (>10MB) |
| Others | **No** | Must use Playwright scraping |

---

## Implementation Plan

### Architecture: Config-Driven Custom Scrapers

```
scrapers/custom/
    __init__.py
    base_scraper.py             # Shared Playwright utilities (Phase 2)
    google_rss_fetcher.py       # XML parser (no Playwright needed)
    custom_scraper.py           # Config-driven Playwright scraper (Phase 2)

config/custom/
    employers.yaml              # Employer configs with selectors
    selector_templates.yaml     # Reusable selector sets (Taleo, Phenom)
    title_patterns.yaml         # Reuse from Greenhouse
    location_patterns.yaml      # Reuse from Greenhouse
```

### Phase 1: Foundation + Google XML [COMPLETE]

**Goal**: Build base infrastructure + easiest win (Google XML feed)

**Tasks**:
- [x] Create `scrapers/custom/` directory structure
- [x] Build `google_rss_fetcher.py` - Parse Google's XML feed
- [x] Create `config/custom/employers.yaml` with initial employer list
- [x] Create `config/custom/selector_templates.yaml` with Taleo/Phenom/Workday templates
- [x] Add `DataSource.CUSTOM` to unified ingester
- [x] Integrate Google XML into pipeline (`process_custom_incremental()`)
- [x] Add `--employers` CLI argument for custom source
- [x] Fix `extract_job_id()` bug for empty URLs (use UUID)
- [x] Fix XML parser for Google's actual format (not RSS - custom `<jobs><job>` structure)
- [x] Test Google XML parsing end-to-end
- [x] Update DB `valid_source` constraint to include 'custom'
- [x] Fix `process_custom_incremental()` bugs (nested classification, function signatures)
- [x] Add `--source` filter to backfill utility
- [x] Backfill 63 Google jobs to enriched_jobs (100% success rate)

**Files Created**:
- `scrapers/custom/__init__.py`
- `scrapers/custom/google_rss_fetcher.py` (~465 lines)
- `config/custom/employers.yaml` (9 employers configured)
- `config/custom/selector_templates.yaml` (5 ATS templates)

**Google XML Feed** (no Playwright needed):
- URL: `https://www.google.com/about/careers/applications/jobs/feed.xml`
- Free, unlimited, official source
- **NOT RSS** - custom XML format with `<jobs><job>` structure
- Includes: title, description, locations, salary (in description), team/employer
- Reuses Greenhouse title/location patterns for filtering

**Final Results (2026-01-08)**:
| Metric | Count |
|--------|-------|
| Total jobs in feed | 2,516 |
| Filtered by title | ~2,000 |
| Filtered by location | ~200 |
| **Jobs matching filters** | **278** |
| Jobs processed (backfill) | 63 |
| Jobs in enriched_jobs | 63 |
| Success rate | 100% |

**Classification Notes**:
- ~48% of jobs required fallback to `gemini-2.5-flash` due to JSON parsing errors from `gemini-3-flash-preview`
- Fallback adds ~50-60 seconds per job but achieves 100% success
- Most Google jobs classified as `out_of_scope` (Software Engineers) - this is CORRECT per taxonomy (platform focuses on Product, Data, Delivery roles)
- Product Manager roles correctly classified as `product_management`

Sample data quality:
- Location: "Mountain View, CA, USA", "New York, NY, USA", "Singapore"
- Team: "YouTube", "Google Cloud", etc.
- Salary: "$141,000 - $202,000 USD" (extracted from description)
- Full descriptions with qualifications and responsibilities

### Phase 2: Playwright Base + First Custom Scrapers [FUTURE]

**Goal**: Build reusable Playwright infrastructure + 2-3 employers

**Prerequisites**:
- Clear business need for specific employer coverage
- Time to maintain selectors (expect monthly breakage)

**Tasks**:
- [ ] Create `base_scraper.py` with shared Playwright utilities
- [ ] Create `custom_scraper.py` - config-driven scraper
- [ ] Build selector configs for first employers:
   - **Apple** (Medium difficulty, clean React structure)
   - **Netflix** (Medium, external job board)
   - **JPMorgan** (Taleo template - reusable for other banks)
- [ ] Test and validate selectors
- [ ] Add retry/error handling for flaky selectors

**Priority order** (easiest first):
1. Apple - Clean structure, good starting point
2. Netflix - External platform, may have simpler DOM
3. JPMorgan - Taleo template (reusable for Goldman, Morgan Stanley)

**Estimated effort**: 2-3 days per employer initially, ongoing maintenance

### Phase 3: Expand Coverage [FUTURE]

**Goal**: Add more employers using learned patterns

**Tasks**:
- [ ] Add Microsoft (Phenom platform)
- [ ] Add Goldman Sachs, Morgan Stanley (Taleo template)
- [ ] Add Amazon, Meta (harder - heavy JS SPAs)
- [ ] Create Phenom selector template if patterns emerge
- [ ] Document selector maintenance procedures

**Note**: Amazon and Meta are particularly challenging due to heavy JS SPAs and potential anti-bot measures.

### Phase 4: Automation [FUTURE]

**Goal**: Monthly scheduled scraping

**Tasks**:
- [ ] Create GitHub Action workflow `scrape-custom.yml`
- [ ] Schedule monthly runs (jobs turn over ~30 days)
- [ ] Add monitoring/alerting for selector failures
- [ ] Document selector update procedures
- [ ] Consider Google XML on weekly schedule (low cost, high value)

---

## Architecture Review (2026-01-08)

**Reviewer**: system-architect skill
**Overall Assessment**: GOOD

### Strengths

| Aspect | Rating | Notes |
|--------|--------|-------|
| Pattern Consistency | Good | Follows Lever/Ashby patterns exactly |
| Config-Driven Design | Good | Template system is elegant and extensible |
| Separation of Concerns | Good | Fetcher/config/pipeline properly separated |
| Extensibility | Good | Phase 2 Playwright path well-designed |

### Key Decisions Made

| Decision | Rationale |
|----------|-----------|
| Single `employers.yaml` | Keeps all enterprise config in one place |
| Reuse Greenhouse filters | Consistency, single source of truth |
| `DataSource.CUSTOM` (not per-employer) | Simpler enum, custom scraper jobs are supplementary |
| Config-driven Playwright selectors | Allows selector updates without code changes |

### Technical Debt Identified

1. **Filter function duplication** - `strip_html()`, `is_relevant_role()`, `matches_target_location()` duplicated from Greenhouse
   - **Recommendation**: Extract to `scrapers/shared/filters.py` (can defer)

2. **fetch_jobs.py growing large** - Now 2900+ lines with enterprise addition
   - **Recommendation**: Consider modularizing `process_*_incremental` functions (future)

3. ~~**Bug in extract_job_id()** - Empty URL edge case returns hash of empty string~~ [FIXED]
   - Now uses UUID for empty URLs

4. **XML format assumption** - Feed is NOT RSS, it's custom XML [FIXED]
   - Parser updated to handle `<jobs><job>` structure

### Next Steps (Immediate) - ALL COMPLETE

1. ~~Fix `extract_job_id()` empty URL bug~~ [DONE]
2. ~~Test Google XML feed parsing locally~~ [DONE - 278 jobs match filters]
3. ~~Validate XML feed structure matches assumptions~~ [DONE - fixed parser]
4. ~~Update DB constraint~~ [DONE - added 'custom' to `valid_source` check]
5. ~~Run full pipeline with classification + storage~~ [DONE - 63 jobs backfilled]

---

## Success Metrics

**Phase 1 (Google XML)** - [COMPLETE]:
- [x] Successfully parse Google XML feed (2,516 jobs parsed)
- [x] Find 50+ relevant jobs in target locations/families (278 matched)
- [x] Description quality sufficient for classification (full descriptions with salary)
- [x] Integrated into pipeline with `--sources custom --employers google`
- [x] DB constraint updated and jobs stored successfully (63 jobs in enriched_jobs)
- [x] Classification works correctly (100% success rate with fallback)

**Phase 2 (First Playwright Scrapers)** - [FUTURE]:
- [ ] Apple scraper working with stable selectors
- [ ] Netflix scraper working
- [ ] JPMorgan (Taleo) scraper working + template created

**Phase 3 (Expanded Coverage)** - [FUTURE]:
- [ ] 5+ enterprise employers actively scraped
- [ ] Taleo template reused for multiple banks
- [ ] Monthly automated workflow running

**Overall**:
- [x] No duplicate jobs with existing ATS sources (MD5 hash dedup works)
- [x] Classification accuracy comparable to existing sources
- [ ] Selector updates take <30 minutes per employer (not yet tested)

---

## Lessons Learned (Phase 1)

### What Worked Well

1. **Config-driven design** - Reusing Greenhouse title/location patterns was efficient
2. **XML feed discovery** - Google's official feed is high quality and unlimited
3. **Backfill utility** - `--source` filter made it easy to process custom jobs separately
4. **Fallback mechanism** - `gemini-2.5-flash` fallback achieves 100% success despite preview model issues

### Challenges Encountered

1. **XML format assumption** - Initially assumed RSS format, but Google uses custom `<jobs><job>` structure
2. **Nested classification results** - `classify_job()` returns nested dict (`role.job_family`), not flat
3. **Function signature mismatches** - Several pipeline functions had different signatures than expected
4. **Preview model instability** - `gemini-3-flash-preview` produces malformed JSON ~48% of the time

### Recommendations for Future Phases

1. **Test with real data early** - Don't assume API/feed formats match documentation
2. **Consider stable Gemini model** - For custom source, may want to skip preview model
3. **Add integration tests** - Mock the full pipeline path to catch signature mismatches
4. **Document all function signatures** - Especially for `classify_job()`, `is_agency_job()`, etc.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Site structure changes | Config-driven selectors allow quick updates without code changes |
| Heavy JS SPAs (Amazon, Meta) | Start with easier targets (Google RSS, Apple), tackle harder ones later |
| Anti-bot detection | Use realistic browser fingerprints, add delays, rotate user agents |
| Selector maintenance burden | Create reusable templates for common ATS platforms (Taleo, Phenom) |
| Rate limiting | Implement delays between requests, run monthly (not daily) |

---

## Maintenance Procedures

### When Selectors Break

1. **Detect**: Pipeline logs show 0 jobs for an employer
2. **Debug**: Use `PWDEBUG=1` to open Playwright Inspector
3. **Update**: Modify selectors in `config/custom/employers.yaml`
4. **Test**: Run single employer: `--sources custom --employers apple`
5. **Deploy**: Commit config change

### Adding New Employers

1. Visit careers page, inspect DOM structure
2. Identify: job card, title, location, URL selectors
3. Determine pagination type (scroll, next button, page numbers)
4. Add config to `employers.yaml`
5. Test with `--dry-run`
6. Enable and run

---

## References

- [Microsoft Careers (Phenom)](https://www.phenom.com/blog/check-out-microsofts-career-site-powered-by-phenom-people)
- [Google Careers XML Feed](https://careers.google.com/jobs/feed.xml) (NOT RSS - custom format)
- [Workday Market Share - SHRM](https://www.shrm.org/resourcesandtools/hr-topics/talent-acquisition/pages/workday-ats-is-top-choice-of-fortune-500.aspx)
- [Apify LinkedIn Scrapers](https://apify.com/happitap/linkedin-job-scraper) (fallback option)

---

## Future Considerations

### Quick Wins Available Now

1. **Schedule Google XML scraping** - Add to GitHub Actions (weekly or bi-weekly)
   - Low effort: Just add workflow file
   - High value: 278 jobs from one of the largest tech employers

2. **Process remaining ~215 Google jobs** - Run pipeline without --limit
   - Most will be `out_of_scope` (Software Engineering)
   - ~10-20% may be relevant Product/Data/Delivery roles

### When to Pursue Phase 2 (Playwright)

Consider Phase 2 when:
- Specific employer coverage is requested (e.g., "I need Apple jobs")
- Greenhouse/Lever/Ashby coverage gaps are identified for key employers
- Time is available for ongoing selector maintenance

**Cost-benefit**: Each Playwright scraper requires:
- Initial: 2-3 days development + testing
- Ongoing: ~2-4 hours/month maintenance (selector fixes)

### Alternatives to Custom Scrapers

If Phase 2 becomes necessary but maintenance burden is too high:

| Alternative | Cost | Coverage | Maintenance |
|-------------|------|----------|-------------|
| Apify LinkedIn Scraper | ~$1/1000 jobs | Broad | None (managed service) |
| TheirStack API | Subscription | Enterprise focus | None |
| Manual curation | Time | Targeted | Low |

### Recommended Next Actions

1. **Short-term**: Add `scrape-custom.yml` GitHub Action for Google XML (weekly)
2. **Monitor**: Track if Google jobs appear in dashboard searches
3. **Defer**: Playwright scrapers until specific employer need arises
4. **Consider**: Switching to stable Gemini model for custom source to reduce fallback overhead
