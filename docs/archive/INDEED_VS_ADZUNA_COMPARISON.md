# Indeed API vs Adzuna API - Comparison for Job Analytics

## Executive Summary

**Key Finding:** Indeed has deprecated their public Job Search API and moved to partner-only APIs. You cannot simply swap Indeed for Adzuna without business partnership.

If full-text job descriptions are critical, Indeed and LinkedIn are better alternatives, but they require business approval/partnership.

## Indeed API Status (2025)

### ⚠️ CRITICAL: Job Search API is DEPRECATED

**Official Status:** The Indeed Job Search API is **no longer available for new integrations** as of 2024-2025.

**Available APIs (2025):**
1. **Job Sync API** (GraphQL) - For ATS partners to post jobs
2. **Disposition Sync API** - For ATS partners to sync candidate dispositions
3. **Private API Reference** - Access-restricted, requires partnership

### What This Means

You **cannot use Indeed as a drop-in replacement** for Adzuna without:
- Business partnership with Indeed
- Approval from Indeed's partnerships team
- Implementation of their Job Sync API (if you're building an ATS)

## Adzuna API - Current Status

### ✅ Still Available & Widely Used

**Status:** Fully operational public API
**Access:** Free with API key
**Availability:** No partnership required
**Job Search:** Works well with keyword/location filters
**Major Limitation:** **Full job descriptions are truncated** (100% of jobs)

### Sample Adzuna Response

```json
{
  "job_id": 1234567,
  "title": "Data Engineer",
  "company": "Stripe",
  "location": "San Francisco",
  "description": "We are looking for a Data Engineer to join our team... [TRUNCATED]",
  "url": "https://www.adzuna.co.uk/jobs/details/1234567"
}
```

**Problem:** The `description` field is always limited to ~250-300 characters, cutting off critical requirements.

## Alternatives to Consider

### Option 1: Indeed (If Business Partnership Possible)

**Advantages:**
- ✅ Larger job database than Adzuna
- ✅ More complete job descriptions
- ✅ Good international coverage
- ✅ Structured data available

**Disadvantages:**
- ❌ Requires business partnership
- ❌ Job Search API deprecated
- ❌ May require payment
- ⚠️ Need to apply for partnership program

**Getting Access:**
1. Contact Indeed's developer/partnerships team
2. Apply for partner program
3. Wait for approval (2-6 weeks typical)
4. Implement Job Sync API or get access to partner APIs
5. Start fetching jobs

**Estimated Timeline:** 4-8 weeks
**Cost:** Likely paid, terms depend on partnership agreement

---

### Option 2: LinkedIn (Recommended if Possible)

**LinkedIn Jobs API:**
- ✅ Full job descriptions available
- ✅ Highest quality data
- ✅ Excellent coverage for tech roles
- ✅ Rich metadata (seniority, employment type, etc.)

**Disadvantages:**
- ❌ Requires LinkedIn business approval
- ❌ Stricter rate limits
- ❌ Only available to LinkedIn Official Partners
- ⚠️ Terms of service restrictions

**Getting Access:**
1. Apply for LinkedIn API partnership
2. Demonstrate legitimate business use case
3. Wait for approval (4-12 weeks typical)
4. Implement LinkedIn Jobs API
5. Start fetching jobs

**Estimated Timeline:** 6-12 weeks
**Cost:** Likely paid, terms vary

**Advantage Over Indeed:** LinkedIn has much better job description completeness and company data.

---

### Option 3: Keep Adzuna + Selective Web Scraping

**Hybrid Approach:**
- Keep Adzuna as primary source (available now, free)
- Selectively scrape full text from company ATS for key jobs
- Use Adzuna text for remaining jobs
- Accept classifier will have mixed accuracy

**Advantages:**
- ✅ No partnership needed
- ✅ Can start immediately
- ✅ Full control over scraping
- ✅ Cost-effective

**Disadvantages:**
- ❌ Still leaves 70%+ with truncated text
- ⚠️ Web scraping is slower
- ⚠️ May violate some company ToS
- ⚠️ High maintenance (sites change)

**Estimated Timeline:** 1-2 weeks (Phase 1 + 2 from earlier recommendations)
**Cost:** Dev time only

---

### Option 4: Switch to Open Job Board

**Job boards with full APIs:**
- **Stack Overflow Jobs** (if you want tech-focused)
- **Angel List** (startups)
- **SmartRecruiters Public Jobs** (some companies use this)
- **Greenhouse** (some companies publish publicly)

**Advantages:**
- ✅ Open APIs available
- ✅ Full job descriptions
- ✅ No partnership needed

**Disadvantages:**
- ❌ Much smaller job set
- ❌ Skewed toward tech companies
- ❌ Won't have broad coverage of your London data

---

## Comparison Table

| Aspect | Adzuna | Indeed | LinkedIn | Web Scraping |
|--------|--------|--------|----------|--------------|
| **Public API Available** | ✅ Yes | ❌ No (deprecated) | ❌ Partnership only | N/A |
| **Full Descriptions** | ❌ No (truncated) | ✅ Yes | ✅ Yes | ✅ Yes |
| **Job Coverage** | Large | Very Large | Large | Selective |
| **International** | ✅ Yes | ✅ Yes | ✅ Yes | Yes |
| **Start Time** | Immediate | 4-8 weeks | 6-12 weeks | 1-2 weeks |
| **Cost** | Free | Likely $$ | Likely $$$ | Dev time |
| **Partnership Needed** | ❌ No | ✅ Yes | ✅ Yes | ❌ No |
| **Implementation Complexity** | Low | High | High | Medium |
| **Data Quality** | Good | Excellent | Excellent | Variable |
| **Rate Limits** | Generous | TBD | Strict | TBD |

## Recommendation

### For Your Use Case (London data, mixed industries)

**Ranking by feasibility & effectiveness:**

1. **BEST IMMEDIATE: Keep Adzuna + Manual Audit** (My previous recommendation)
   - You already have Adzuna data
   - Audit top 20-30 companies manually
   - Build targeted web scrapers (1-2 weeks)
   - Achieve 20-30% full-text coverage
   - Cost: Dev time only
   - Timeline: 1-2 weeks

2. **BEST LONG-TERM: Apply for LinkedIn Partnership**
   - LinkedIn has best job description completeness
   - Better for UK market coverage
   - Timeline: 6-12 weeks to get approval
   - Start the application NOW while working on other improvements
   - Cost: Likely partnership fees

3. **FALLBACK: Indeed Partnership (Lower Priority)**
   - Requires business partnership
   - Job Search API deprecated
   - Less elegant than LinkedIn
   - But possibly simpler terms

4. **DO NOT: Immediately Pivot Away from Adzuna**
   - Adzuna still works fine as discovery source
   - Don't spend time building replacement right now
   - Focus on improving classifier with truncated text instead

## Action Items

### This Week
- [ ] Decide between options (Adzuna + scraping vs. LinkedIn partnership vs. hybrid)
- [ ] If going with Adzuna + scraping: Do manual audit of top 20 companies
- [ ] If going with LinkedIn: Start partnership application

### This Month
- [ ] If Adzuna + scraping: Build and test parsers for discovered ATS
- [ ] If LinkedIn: Follow up on partnership application status

### Next Quarter
- [ ] Evaluate results
- [ ] If successful, expand
- [ ] Consider LinkedIn as longer-term solution

## Resources

**Indeed Developer:**
- https://docs.indeed.com/ (partnership/partner-only content)
- https://opensource.indeedeng.io/ (open-source projects only)

**LinkedIn Jobs API:**
- Apply here: https://business.linkedin.com/talent-solutions/recruiting-software
- Reference: LinkedIn Official Partners Program

**Web Scraping:**
- BeautifulSoup (HTML parsing)
- Selenium/Playwright (browser automation)
- RateLimit handling (respect robots.txt)

## Questions to Answer

Before proceeding, clarify:

1. **Is full-text coverage of 100% jobs critical?**
   - If yes → invest in LinkedIn partnership or Indeed
   - If no → Adzuna + selective scraping is fine

2. **What's your timeline?**
   - If urgent (1-2 weeks) → Keep Adzuna + manual audit
   - If flexible (2-3 months) → Invest in LinkedIn partnership

3. **What's your budget?**
   - If low cost → Adzuna + scraping
   - If budget available → LinkedIn or Indeed partnership

4. **Can your classifier improve without full text?**
   - If yes → Keep Adzuna, improve classifier
   - If no → Need full text (requires partnership or scraping)

## Conclusion

**Do not attempt to swap Indeed for Adzuna directly.** Indeed's public API is deprecated.

Instead, choose one of the four options above based on your timeline and budget. The most practical immediate solution is **keeping Adzuna and selectively scraping company ATS sites** for the 20-30% of jobs where full text is most valuable.

Would you like me to help with:
1. Starting the LinkedIn partnership application process?
2. Continuing with the Adzuna + web scraping approach?
3. Something else?
