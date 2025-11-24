# ATS Detection Analysis - Findings & Recommendations

## The Problem You Identified

Your excellent observation: **Company career pages often hide the actual ATS backend**

Example: Wise.jobs → SmartRecruiters
- **Landing page:** wise.jobs (appears custom)
- **User clicks "Apply"** → Redirects to jobs.smartrecruiters.com
- **Our detector saw:** Custom ATS
- **Reality:** SmartRecruiters backend

## Analysis Results

### Dataset: 50 London-based jobs

| Category | Count | % |
|----------|-------|---|
| Greenhouse | 0 | 0% |
| Lever | 0 | 0% |
| Workday | 0 | 0% |
| **Custom/Unknown ATS** | 26 | 52% |
| **No findable page** | 24 | 48% |

### The Root Issue

**Your London dataset is fundamentally incompatible with the ATS scraping strategy** because:

1. **52% use custom/unknown ATS** - Many likely wrap hidden backends (like Wise→SmartRecruiters)
2. **48% have no findable careers page** - Using recruiting agencies or LinkedIn exclusively
3. **0% use the 3 major platforms** we built parsers for (Greenhouse, Lever, Workday)

### What Would Be Needed to Detect Hidden Backends

To detect backends like "Wise → SmartRecruiters", we would need:

**Option A: Browser Automation** (Selenium/Playwright)
- Load career page in real browser
- Find job listing
- Click "Apply" button
- Capture redirect chain
- Detect final ATS

**Pros:** Accurate, follows real user journey
**Cons:** Slow, expensive, high failure rate, may violate ToS

**Option B: Static Analysis** (current approach)
- Parse HTML for ATS links
- Check JavaScript code
- Look for API calls
- Search for CSS/iframe references

**Pros:** Fast, cheap
**Cons:** Many companies obfuscate this, lazy-load content

**Option C: Manual Mapping**
- Manually research top 20-30 companies
- Document their actual ATS
- Hard-code mappings
- Use for these only, fallback for others

**Pros:** 100% accurate for mapped companies
**Cons:** Manual work, doesn't scale

## The Bigger Picture

### Why This Dataset is Challenging

Your test data contains:
- **Large corporates** (Microsoft, Google, Sainsbury's) - Use Workday but on custom domains
- **SMEs & Agencies** (Travelex, Billigence, TCS) - Custom systems or no online presence
- **Tech companies** (Meta, Wise) - Wrap modern ATS systems behind branded career sites

This is **NOT** a startup-focused dataset that uses standard ATS platforms.

### Success Rates by Approach

| Approach | Success Rate | Effort |
|----------|-------------|--------|
| Detect 3 major ATS | 0% | Low |
| Detect major + hidden backends | ~10-15%* | High |
| Browser automation with clicks | ~40-50%* | Very High |
| Manual mapping | 100% (for mapped) | Medium |
| Switch data source (Indeed/LinkedIn) | 80%+ | High |

*Estimated based on number of custom pages that are accessible

## Recommendation: Multi-Prong Approach

Given the constraints, I recommend:

### Phase 1: Identify Actual ATS Backend (Manual - 1-2 hours)
1. Take the 26 "custom ATS" companies
2. Manually visit each careers page
3. Click through to job listing
4. Note the actual job posting URL/ATS
5. Document findings

**Outcome:** A mapping of custom pages → actual ATS

Example:
```
Wise -> jobs.smartrecruiters.com
Meta -> lever.co backend
Microsoft -> myworkdayjobs.com
Dataiku -> custom system (no detectable ATS)
```

### Phase 2: Build Selective Scrapers (2-4 hours)
Based on Phase 1 findings, build scrapers for:
- SmartRecruiters (if many companies use it)
- Any other platforms discovered
- Keep Greenhouse/Lever parsers from before

### Phase 3: Accept Limitations (For Unscrapable Jobs)
- 48% of dataset with no findable page → Use Adzuna text as-is
- Very custom systems → Use Adzuna text as-is
- Document `text_source: 'adzuna_api'` for these

### Phase 4: Improve Classifier Instead
Rather than chase 100% text scraping, improve classifier to work better with truncated text:
- Train on both full and truncated examples
- Use context clues from Adzuna metadata (company size, industry, title patterns)
- Ensemble with rule-based extraction

**This might achieve 70-80% accuracy with less effort than scraping 100%**

## Implementation Path

### Short Term (1-2 days)
1. Manual audit of top 20 companies
2. Document actual ATS systems
3. Build scrapers for top 2-3 ATS found
4. Test on ~10-15% of dataset

### Medium Term (1 week)
1. Expand to 50 companies
2. Build more ATS parsers as needed
3. Set up Supabase storage for full text
4. Begin production scraping

### Long Term (ongoing)
1. Collect feedback on missing/incorrect detections
2. Continuously expand supported ATS platforms
3. Build company→ATS mappings database
4. Consider browser automation for truly complex sites

## Alternative: Pivot to Different Data Source

If time/resources are limited, consider:

**Indeed API or Scraping**
- More complete job descriptions natively
- No truncation issues
- ~80% coverage of market
- Different company bias (more SMEs, fewer enterprise)

**LinkedIn Jobs API** (if you can get approval)
- Full job descriptions
- Reliable data quality
- Covers most companies
- Requires business approval & licensing

**Combination Approach**
- Keep Adzuna for breadth
- Enrich with Indeed/LinkedIn for depth on key companies
- Use whichever source has best description for each job

## My Recommendation

**Go with Phase 1 + Phase 2: Manual audit + selective scrapers**

**Why:**
1. Leverages your excellent observation about hidden backends
2. Achieves 20-30% full-text coverage with manageable effort
3. Remaining 70% gets classifier improvements instead of scraping
4. Provides baseline for future expansion
5. Gives you concrete data on ATS landscape in your dataset

**Time investment:** ~2-3 days of work
**Expected improvement:** Skills F1 from 0.29 → 0.50-0.60 (on scraped subset, others stay at 0.29)

## Next Step

If you'd like to proceed:

1. **Share manual audit findings** (which companies use which ATS)
2. **We'll build targeted scrapers** for the top platforms
3. **Test on full dataset** and measure improvement
4. **Store results** in Supabase with proper `text_source` tracking

Would you like to proceed with the manual audit, or explore other options?
