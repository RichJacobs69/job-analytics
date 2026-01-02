# Security Audit Skill

**Purpose:** Comprehensive security audit of the job analytics platform, testing actual entry points and generating actionable, prioritized remediation reports for MVP-stage security hardening.

**Trigger:** User requests security audit, vulnerability assessment, or pre-launch security review.

## Scope

- **Backend:** API endpoints, Supabase configuration, secrets management, GitHub Actions
- **Frontend:** Next.js dashboard, XSS/CSRF risks, security headers
- **Infrastructure:** Environment variables, dependencies, error handling
- **Data Protection:** PII exposure, logging practices, public data limits

## Process

### Phase 1: Discovery & Enumeration

**1.1 Map Entry Points**
- [ ] Find all API routes (Next.js `/api/**/*.ts`, `/api/**/*.js`)
- [ ] Identify public endpoints vs authenticated endpoints
- [ ] List Supabase tables and their public exposure
- [ ] Catalog frontend pages that consume APIs
- [ ] Document external integrations (Adzuna, Gemini, Anthropic, Playwright)

**1.2 Identify Credential Storage**
- [ ] Check `.env` files exist and are gitignored
- [ ] Scan for hardcoded API keys in codebase
- [ ] Review environment variable usage patterns
- [ ] Check GitHub Actions secrets configuration

### Phase 2: Active Security Testing

**2.1 API Endpoint Testing**

For each discovered API endpoint:
- [ ] Test unauthenticated access (should fail appropriately)
- [ ] Test with malformed input (SQL injection, XSS payloads)
- [ ] Test rate limiting (make 50+ rapid requests)
- [ ] Check error messages for information disclosure
- [ ] Verify CORS headers are restrictive
- [ ] Test for IDOR vulnerabilities (parameter tampering)

**Example Tests:**
```bash
# Test public job feed endpoint
curl -X GET https://your-domain.com/api/hiring-market/jobs/feed
curl -X GET "https://your-domain.com/api/hiring-market/jobs/feed?limit=99999"
curl -X GET "https://your-domain.com/api/hiring-market/jobs/feed?id=1' OR '1'='1"

# Test job detail endpoint
curl -X GET https://your-domain.com/api/hiring-market/jobs/[id]/context
curl -X GET https://your-domain.com/api/hiring-market/jobs/../../../etc/passwd/context

# Check response headers
curl -I https://your-domain.com/
```

**2.2 Supabase Security Testing**

- [ ] Check if service role key is used in frontend code
- [ ] Test RLS policies on `enriched_jobs` table
- [ ] Test RLS policies on `employer_fill_stats` table
- [ ] Test RLS policies on `url_status` column access
- [ ] Verify anon key has read-only access
- [ ] Test direct SQL injection via Supabase client
- [ ] Check if table schemas are publicly queryable

**Example Tests:**
```bash
# Test direct table access with anon key
curl "https://YOUR_PROJECT.supabase.co/rest/v1/enriched_jobs" \
  -H "apikey: ANON_KEY" \
  -H "Authorization: Bearer ANON_KEY"

# Test unauthorized write
curl -X POST "https://YOUR_PROJECT.supabase.co/rest/v1/enriched_jobs" \
  -H "apikey: ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title": "malicious job"}'

# Test RLS bypass attempts
curl "https://YOUR_PROJECT.supabase.co/rest/v1/enriched_jobs?select=*&limit=10000" \
  -H "apikey: ANON_KEY"
```

**2.3 Frontend Security Testing**

- [ ] Check for XSS vulnerabilities in job descriptions
- [ ] Verify CSP headers are present
- [ ] Test for CSRF protection on any forms
- [ ] Check if API keys are exposed in client bundle
- [ ] Verify security headers (X-Frame-Options, X-Content-Type-Options)
- [ ] Test for clickjacking vulnerabilities

**2.4 Secrets & Credential Scanning**

- [ ] Scan all code files for API key patterns
- [ ] Check git history for accidentally committed secrets
- [ ] Verify `.env` is in `.gitignore`
- [ ] Check if error messages leak credentials
- [ ] Review GitHub Actions logs for exposed secrets

**Patterns to grep for:**
- `ADZUNA_APP_ID`
- `ADZUNA_API_KEY`
- `ANTHROPIC_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `GEMINI_API_KEY`
- Hardcoded URLs with tokens

**2.5 Dependency & Infrastructure**

- [ ] Run `npm audit` for frontend vulnerabilities
- [ ] Run `pip-audit` or `safety check` for Python vulnerabilities
- [ ] Check for outdated critical dependencies
- [ ] Review GitHub Actions workflow permissions
- [ ] Verify HTTPS enforcement (no HTTP fallback)

### Phase 3: Report Generation

**3.1 Create Security Audit Report**

Generate `SECURITY_AUDIT_REPORT.md` with:

**Structure:**
```markdown
# Security Audit Report
**Date:** YYYY-MM-DD
**Auditor:** Claude (Security Audit Skill)
**Project:** Job Analytics Platform

## Executive Summary
[High-level overview of security posture]

## Critical Findings (Fix Before Launch)
[P0 issues that must be addressed]

## High Priority (Fix Within 1 Week)
[P1 issues for MVP hardening]

## Medium Priority (Fix Before Scale)
[P2 issues to address before user growth]

## Low Priority (Nice to Have)
[P3 improvements for future]

## Detailed Findings

### [CRITICAL/HIGH/MEDIUM/LOW] Finding Title
**Category:** [API Security | Credential Management | Data Protection | etc.]
**Risk:** [Description of potential impact]
**Evidence:** [What was tested, what failed]
**Remediation:** [Specific code changes needed]
**Effort:** [Low | Medium | High]

## Compliance Checklist
- [ ] OWASP Top 10 Review
- [ ] API Security Best Practices
- [ ] Data Protection (GDPR considerations)
- [ ] Secure Development Lifecycle

## Next Steps
[Prioritized action items]
```

**3.2 Prioritization Criteria**

| Priority | Criteria | Examples |
|----------|----------|----------|
| **Critical (P0)** | Actively exploitable, data breach risk, credential exposure | Exposed service role key, no RLS policies, SQL injection |
| **High (P1)** | Easy to exploit, abuse potential, DoS risk | No rate limiting, missing input validation, verbose errors |
| **Medium (P2)** | Harder to exploit, limited impact, best practice | Missing security headers, weak CORS, outdated deps |
| **Low (P3)** | Defense in depth, future-proofing | Additional logging, security monitoring, CSP refinement |

**3.3 MVP-Appropriate Fixes**

Focus on:
- **High ROI, low effort:** Environment variable checks, .gitignore fixes
- **User trust essentials:** HTTPS, basic RLS, API key protection
- **Abuse prevention:** Rate limiting, input validation on public endpoints
- **Avoid over-engineering:** Don't require OAuth, RBAC, or WAF at this stage

## Testing Checklist

Before running audit, ensure:
- [ ] `.env` file is present and loaded
- [ ] You have the deployed URL (if testing production)
- [ ] Supabase project URL is known
- [ ] You can make HTTP requests (curl available)

## Execution Steps

1. **Run Discovery:**
   - Use Glob to find API routes: `**/{api,pages/api}/**/*.{ts,js,tsx,jsx}`
   - Use Glob to find frontend pages: `**/pages/**/*.{ts,tsx,js,jsx}`
   - Use Read to examine Supabase client initialization
   - Use Grep to find all environment variable references

2. **Execute Tests:**
   - Use Bash to run curl commands against endpoints
   - Use Bash to test Supabase REST API directly
   - Use Grep with regex patterns for secret scanning
   - Use Bash to run `npm audit` and `pip-audit`

3. **Document Findings:**
   - Create detailed notes for each test
   - Capture actual curl responses showing vulnerabilities
   - Screenshot or log any error messages
   - Record specific line numbers of code issues

4. **Generate Report:**
   - Use Write to create `SECURITY_AUDIT_REPORT.md`
   - Include code snippets showing vulnerable patterns
   - Provide exact remediation steps with before/after code
   - Link to relevant security best practice docs

5. **Create Action Plan:**
   - Use TodoWrite to create prioritized fix list
   - Estimate effort for each remediation
   - Group related fixes that can be done together

## Tools Used

- **Glob:** Discover API routes, pages, config files
- **Grep:** Scan for secrets, vulnerable patterns, environment vars
- **Bash:** Execute curl tests, run security audits (npm audit, pip-audit)
- **Read:** Review code for security anti-patterns
- **Write:** Generate comprehensive security report
- **TodoWrite:** Create prioritized remediation task list

## Output Artifacts

1. `SECURITY_AUDIT_REPORT.md` - Full audit report
2. `docs/security/REMEDIATION_PLAN.md` - Prioritized fix plan (optional)
3. TodoWrite list with P0/P1 items ready to implement

## MVP Security Baseline

For early-stage product, ensure:
- [x] No exposed credentials in code or git history
- [x] Basic Supabase RLS on public tables
- [x] Rate limiting on public API endpoints
- [x] Input validation on user-provided parameters
- [x] HTTPS enforced on production
- [x] Error messages don't leak sensitive info
- [x] Dependencies have no critical CVEs
- [x] GitHub Actions secrets are properly scoped

## Notes

- This skill performs **live testing** - ensure you have permission to test production endpoints
- Some tests may trigger rate limits or alerts - coordinate with monitoring
- False positives are possible - validate findings before remediating
- Re-run this audit before each major release or after adding public features
