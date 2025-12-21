# Agency Blacklist Maintenance Workflow
# How to identify and add new agencies to the blacklist

## MONTHLY MAINTENANCE ROUTINE

### Step 1: Find Potential New Agencies

Run this query to find high-volume employers that might be agencies:

```sql
-- Find employers with suspicious patterns
SELECT 
    employer_name,
    COUNT(*) as job_count,
    is_agency,
    agency_confidence,
    -- Check for agency keywords in name
    CASE 
        WHEN employer_name ILIKE '%recruitment%' THEN '[FLAG] recruitment'
        WHEN employer_name ILIKE '%staffing%' THEN '[FLAG] staffing'
        WHEN employer_name ILIKE '%talent%' THEN '[FLAG] talent'
        WHEN employer_name ILIKE '%resourcing%' THEN '[FLAG] resourcing'
        WHEN employer_name ILIKE '%search%' THEN '[FLAG] search'
        ELSE '[OK] clean'
    END as keyword_flag
FROM enriched_jobs
WHERE posted_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY employer_name, is_agency, agency_confidence
HAVING COUNT(*) >= 3  -- Focus on high-volume posters
ORDER BY job_count DESC, is_agency DESC
LIMIT 50;
```

**Look for:**
- [OK] High job count (5+ jobs/month)
- [OK] Generic job titles across different roles
- [OK] `is_agency=false` but has suspicious keywords
- [OK] Multiple contract positions
- [OK] Vague company names ("Solutions", "Group", "Associates")

---

### Step 2: Manual Research

For each suspicious employer:

1. **Google search:** `"[Company Name]" recruitment agency`
2. **Check their website:** Look for phrases like:
   - "We place candidates"
   - "Recruitment services"
   - "Staffing solutions"
   - "Our clients include..."
3. **Check LinkedIn:** Company type shows "Staffing and Recruiting"
4. **Check job postings:** Multiple unrelated roles = likely agency

---

### Step 3: Add Confirmed Agencies to Blacklist

```bash
# 1. Edit the blacklist file
nano config/agency_blacklist.yaml

# 2. Add to hard_filter section (keep alphabetical and lowercase)
hard_filter:
  # ... existing entries
  - mystery staffing ltd     # ← Add new agency
  - tech talent solutions    # ← Add new agency
```

**Important:** 
- Always use lowercase
- Include full legal name if known
- Add common variations (e.g., "tenth revolution" and "tenth revolution group")

---

### Step 4: Reprocess Existing Jobs

After updating the blacklist, reprocess ALL jobs to fix past misclassifications:

```bash
# Preview changes (DRY RUN)
python backfill_agency_flags.py --force --dry-run

# Review output - look for 🔧 correction icons
# These are jobs that were is_agency=false but are now being corrected

# Apply changes
python backfill_agency_flags.py --force

# Verify
python backfill_agency_flags.py --verify
```

**The `--force` flag is critical here!** Without it, jobs with `is_agency=false` won't be reprocessed. This shows it's being corrected

---

### Step 5: Document Your Changes

```bash
# Update metadata in agency_blacklist.yaml
metadata:
  last_updated: "2025-12-14"  # ← Update date
  total_agencies: 52          # ← Update count
```

Create a log entry:
```bash
# Create/update maintenance log
echo "2025-12-14: Added 3 agencies (Mystery Staffing Ltd, Tech Talent Solutions, Global Search Partners)" >> docs/agency_blacklist_changelog.txt
```

---

## WORKFLOW FOR ADDING A SINGLE AGENCY

If you discover an agency while reviewing data:

### Quick Add Process:

```bash
# 1. Verify it's an agency (Google search)

# 2. Add to blacklist
echo "  - agency name here" >> config/agency_blacklist.yaml

# 3. Reprocess to fix existing jobs
python backfill_agency_flags.py --force

# 4. Future jobs will be blocked automatically
```

---

## EXAMPLE: Full Workflow

### Scenario: You notice "Tech Recruitment Partners" has 8 jobs in your database

**Step 1: Verify it's an agency**
```bash
# Google: "Tech Recruitment Partners"
# Result: LinkedIn shows "Staffing and Recruiting"
# Confirmed: It's an agency
```

**Step 2: Check current classification**
```sql
SELECT 
    employer_name,
    is_agency,
    agency_confidence,
    COUNT(*)
FROM enriched_jobs
WHERE employer_name = 'Tech Recruitment Partners'
GROUP BY employer_name, is_agency, agency_confidence;

-- Result: is_agency=false (WRONG!)
```

**Step 3: Add to blacklist**
```bash
# Edit config/agency_blacklist.yaml
nano config/agency_blacklist.yaml

# Add under hard_filter:
  - tech recruitment partners
```

**Step 4: Reprocess ALL jobs**
```bash
# Force reprocess to fix the 8 existing jobs
python backfill_agency_flags.py --force --dry-run

# Look for:
# 🔧 [X/327] Tech Recruitment Partners → is_agency=True (high)
# ↑ This shows it's being corrected

# Apply
python backfill_agency_flags.py --force
```

**Step 5: Verify correction**
```sql
SELECT 
    employer_name,
    is_agency,
    agency_confidence,
    COUNT(*)
FROM enriched_jobs
WHERE employer_name = 'Tech Recruitment Partners'
GROUP BY employer_name, is_agency, agency_confidence;

-- Result: is_agency=true (FIXED!)
```

**Step 6: Update metadata**
```yaml
# In agency_blacklist.yaml
metadata:
  last_updated: "2025-11-14"
  total_agencies: 50  # Incremented from 49
```

---

## FALSE POSITIVE HANDLING

If a legitimate company is being flagged as an agency:

### Example: "Accenture Solutions" flagged due to "solutions" keyword

**Step 1: Verify it's NOT an agency**
```bash
# Google: "Accenture" 
# Result: Global consulting firm (direct employer)
```

**Step 2: Add to legitimate_companies list**
```bash
nano config/agency_blacklist.yaml

# Add under legitimate_companies:
legitimate_companies:
  - accenture
  - accenture solutions  # ← Add variant
```

**Step 3: Reprocess to fix**
```bash
python backfill_agency_flags.py --force
```

**Step 4: Verify correction**
```sql
SELECT employer_name, is_agency, agency_confidence
FROM enriched_jobs
WHERE employer_name ILIKE '%accenture%';

-- Should show: is_agency=false
```

---

## TESTING NEW ADDITIONS

Before committing blacklist changes:

```python
# Test the updated detection
python -c "
from agency_detection import detect_agency

# Test new agency
is_agency, conf = detect_agency('Tech Recruitment Partners')
print(f'Tech Recruitment Partners: {is_agency} ({conf})')  # Should be True, high

# Test false positive fix
is_agency, conf = detect_agency('Accenture Solutions')
print(f'Accenture Solutions: {is_agency} ({conf})')  # Should be False, low
"
```

---

## MONITORING & ALERTS

Set up a monthly reminder to check for new agencies:

```bash
# Add to crontab (first day of each month)
0 9 1 * * cd /path/to/project && python -c "
import subprocess
result = subprocess.run(['psql', '-c', 'SELECT employer_name, COUNT(*) as jobs FROM enriched_jobs WHERE is_agency=false AND posted_date >= CURRENT_DATE - INTERVAL \"30 days\" GROUP BY employer_name HAVING COUNT(*) >= 5 ORDER BY jobs DESC;'], capture_output=True)
print('High-volume employers to review:', result.stdout.decode())
" | mail -s "Monthly Agency Review" your@email.com
```

---

## BEST PRACTICES

1. Always use `--force` flag when reprocessing after blacklist updates
2. Always use lowercase in agency_blacklist.yaml
3. Always test in dry-run mode before applying changes
4. Always verify with SQL queries after changes
5. Document your changes in metadata and changelog
6. Review monthly for new high-volume agencies
7. Keep legitimate_companies list updated to avoid false positives

---

## TROUBLESHOOTING

### Issue: Agency still showing is_agency=false after adding to blacklist

**Cause:** Forgot to use `--force` flag

**Fix:**
```bash
python backfill_agency_flags.py --force
```

---

### Issue: Legitimate company flagged as agency

**Cause:** Matching pattern in keywords (e.g., "consulting", "solutions")

**Fix:** Add to legitimate_companies list and reprocess

---

### Issue: Backfill says "0 corrections made" but you know there are wrong classifications

**Cause:** Using default mode which only processes NULL values

**Fix:** Use `--force` to reprocess ALL jobs:
```bash
python backfill_agency_flags.py --force
```

---

## SUMMARY

**When to reprocess:**
- [GOOD] After adding agencies to hard_filter → Use `--force`
- [GOOD] After adding companies to legitimate_companies → Use `--force`
- [GOOD] Monthly maintenance routine → Use `--force`
- [NOT NEEDED] Initial setup (all jobs have NULL) → Default mode is fine

**Key commands:**
```bash
# Monthly maintenance
python backfill_agency_flags.py --force --dry-run  # Preview
python backfill_agency_flags.py --force            # Apply
python backfill_agency_flags.py --verify           # Check results

# Initial backfill (one-time)
python backfill_agency_flags.py                    # Process NULLs only
```