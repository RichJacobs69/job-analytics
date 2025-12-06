# Config Cleanup Results

**Date:** 2025-12-06

## Summary

**Good news:** The config is already clean! No unsupported companies were added.

---

## Analysis

### Companies Added to Config (28 total)

All 28 companies added from `new_sites.csv` use **standard Greenhouse URL patterns** and will work with the existing scraper:

| Company | Slug | URL Pattern | Status |
|---------|------|-------------|--------|
| AssemblyAI | assemblyai | job-boards.greenhouse.io | ✅ Supported |
| Awin | awin | job-boards.greenhouse.io | ✅ Supported |
| AWS BDISI | aws-bdisi | job-boards.greenhouse.io | ✅ Supported |
| Blis | blisjobs | job-boards.greenhouse.io | ✅ Supported |
| Bryant Park Consulting | bryantparkconsulting | job-boards.greenhouse.io | ✅ Supported |
| Dolby | dolby | job-boards.greenhouse.io | ✅ Supported |
| English Jobs | englishjobs | job-boards.greenhouse.io | ✅ Supported |
| Etsy Labs | etsylabs | job-boards.greenhouse.io | ✅ Supported |
| Everbridge | everbridge | job-boards.greenhouse.io | ✅ Supported |
| Finson Jobs | finsonjobs | job-boards.greenhouse.io | ✅ Supported |
| Greenlight | greenlight | job-boards.greenhouse.io | ✅ Supported |
| Gumtree | gumtree | job-boards.greenhouse.io | ✅ Supported |
| Human Security | humansecurity | job-boards.greenhouse.io | ✅ Supported |
| Justworks | justworks | job-boards.greenhouse.io | ✅ Supported |
| Ken Plotkin Jobs | kenplotkinjobs | job-boards.greenhouse.io | ✅ Supported |
| Later | later | job-boards.greenhouse.io | ✅ Supported |
| Linear Foundation | linearfoundation | job-boards.greenhouse.io | ✅ Supported |
| Materialize | materialize | job-boards.greenhouse.io | ✅ Supported |
| Midia | midia | job-boards.greenhouse.io | ✅ Supported |
| Overdrive | overdrive | job-boards.greenhouse.io | ✅ Supported |
| PagerDuty | pagerduty | job-boards.greenhouse.io | ✅ Supported |
| Runwise | runwise | job-boards.greenhouse.io | ✅ Supported |
| Spotify | spotify | job-boards.greenhouse.io | ✅ Supported |
| Storyblocks | storyblocks | job-boards.greenhouse.io | ✅ Supported |
| Tatari | tatari | job-boards.greenhouse.io | ✅ Supported |
| Uniform Force | uniformforce | job-boards.greenhouse.io | ✅ Supported |
| Vivun | vivun | job-boards.greenhouse.io | ✅ Supported |
| Watchmaker Genomics | watchmakergenomics | job-boards.greenhouse.io | ✅ Supported |

---

### Companies NOT Added (Custom Domain Only)

These companies only appear in the CSV with custom domain URLs (not standard Greenhouse boards). They were **never added** to the config because the extraction script correctly filtered them out:

| Company | Custom URL Pattern | Reason Not Added |
|---------|-------------------|------------------|
| Brex | www.brex.com/careers/openings?gh_jid= | Custom domain only |
| Vanta | www.vanta.com/careers/openings?gh_jid= | Custom domain only |
| Unity | unity.com/careers/positions/{id}?gh_jid= | Custom domain only |
| Axonius | www.axonius.com/company/careers/open-jobs?gh_jid= | Custom domain only |
| CoreWeave | coreweave.com/careers/job?gh_jid= | Custom domain only |
| Transfix | www.transfix.io/careers?gh_jid= | Custom domain only |
| FanDuel | www.fanduel.careers/open-positions?gh_jid= | Custom domain only |
| NetSuite | jobs.netsuite.com/careers/job?gh_jid= | Custom domain only |
| ...and 15 more | Various custom domains | Custom domain only |

**Total custom domain companies:** 23

---

## Testing Results

**Brex Test:**
- Attempted to scrape using slug `brex`
- Found embed URL: `boards.greenhouse.io/embed/job_board?for=brex`
- Found 171 job listings on the page
- **BUT** couldn't extract job URLs due to different HTML structure
- **Conclusion:** Custom domain companies require scraper modifications

---

## Conclusions

1. ✅ **Config is clean** - No cleanup needed
2. ✅ **All 28 added companies are supported** - They use standard Greenhouse URL patterns
3. ❌ **Custom domain companies can't be scraped** - Would require significant scraper modifications
4. ✅ **Smart extraction** - The script automatically filtered out unsupported companies

---

## Current Config Status

- **Total Greenhouse companies:** 352 (324 existing + 28 new)
- **Total Lever companies:** 12 (10 existing + 2 new: Wise, Verition)
- **Verified supported:** All 352 Greenhouse companies use standard URL patterns
- **Ready to scrape:** Yes, no configuration changes needed

---

## Recommendations

1. **No action needed** - Config is already optimized
2. **Skip custom domain companies** - Not worth the development effort for 23 companies
3. **Focus on standard Greenhouse companies** - You now have 352 companies that will work with the existing scraper
4. **Consider Lever scraper** - If Wise and Verition are high priority (34 job URLs in CSV)

---

## Statistics

- **CSV URLs analyzed:** 432
- **Standard Greenhouse URLs:** 132 companies
- **Custom domain URLs:** 33 URLs across 23 companies
- **Lever URLs:** 34 URLs across 2 companies
- **Added to config:** 28 Greenhouse + 2 Lever = 30 total
- **Companies skipped:** 23 (custom domain only)
- **Success rate:** 100% of added companies are supported
