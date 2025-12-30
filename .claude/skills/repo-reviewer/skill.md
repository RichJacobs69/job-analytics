---
name: repo-reviewer
description: Ruthless repository hygiene reviewer. Use when asked to audit the repo, find duplication, identify stale files, enforce DRY principles, or improve repository structure and organization.
---

# Ruthless Repo Reviewer

Maintain a clean, well-organized repository by identifying duplication, stale content, structural issues, and opportunities to simplify.

## When to Use This Skill

Trigger when user asks to:
- Audit or review the repository
- Find duplicate or redundant content
- Identify stale or outdated files
- Clean up the codebase
- Enforce DRY (Don't Repeat Yourself) principles
- Review documentation organization
- Simplify folder structure
- Find dead code or unused utilities

## Review Philosophy

**Be ruthless but pragmatic:**
- If it's not used, delete it
- If it's duplicated, consolidate it
- If it's stale, archive or update it
- If it's complex, simplify it
- If it's undocumented, document or delete it

## Review Checklist

### 1. Documentation Audit

```bash
# Find all markdown files
find docs -name "*.md" -type f

# Check last modified dates
find docs -name "*.md" -printf "%T@ %Tc %p\n" | sort -n

# Look for potential duplicates by size
find docs -name "*.md" -printf "%s %p\n" | sort -n
```

**Questions to answer:**
- Are there docs in `docs/` that duplicate content in `CLAUDE.md`?
- Are `docs/archive/` files actually archived or still referenced?
- Do `docs/architecture/In Progress/` items have stale status?
- Is `docs/README.md` up to date with current structure?

**Red flags:**
- Multiple files explaining the same concept
- "TODO" or "WIP" in files older than 30 days
- Docs referencing non-existent files or features
- Conflicting information between docs

### 2. Code Duplication

```bash
# Find similar Python files by name
find . -name "*.py" -not -path "./.venv/*" | xargs basename -a | sort | uniq -d

# Check for copy-paste patterns
grep -r "def classify" pipeline/ --include="*.py"
grep -r "def fetch" scrapers/ --include="*.py"
```

**Questions to answer:**
- Are there utility functions duplicated across modules?
- Could shared logic be extracted to a common module?
- Are there multiple implementations of the same pattern?

**Common duplication patterns:**
- Database connection setup in multiple files
- Similar filtering logic across scrapers
- Repeated validation code
- Copy-pasted error handling

### 3. Unused/Dead Code

```bash
# Find Python files not imported anywhere
for f in $(find pipeline -name "*.py" -not -name "__init__.py"); do
  basename=$(basename "$f" .py)
  if ! grep -r "import.*$basename\|from.*$basename" . --include="*.py" -q; then
    echo "Potentially unused: $f"
  fi
done

# Check utilities for one-time scripts
ls -la pipeline/utilities/
```

**Questions to answer:**
- Are `pipeline/utilities/backfill_*.py` scripts still needed?
- Are there commented-out code blocks that should be removed?
- Are there TODO comments that are now done or obsolete?

**Utilities triage:**
| Category | Action |
|----------|--------|
| One-time migration | Archive after confirming complete |
| Periodic maintenance | Keep, document schedule |
| Debugging tool | Keep if actively useful |
| Obsolete | Delete |

### 4. Configuration Sprawl

```bash
# List all config files
find config -type f \( -name "*.yaml" -o -name "*.json" \)

# Check for duplicate keys across configs
# Look for config files that could be consolidated
```

**Questions to answer:**
- Do Greenhouse and Lever configs share patterns that could be unified?
- Are there config values that should be environment variables?
- Is there config documentation explaining each file's purpose?

### 5. Directory Structure

**Current expected structure:**
```
job-analytics/
+-- .claude/skills/     # Claude Code skills
+-- .github/workflows/  # GHA automation
+-- config/             # YAML/JSON configs (by source)
+-- docs/               # Documentation
|   +-- architecture/   # Design docs
|   +-- archive/        # Historical docs
|   +-- costs/          # Cost tracking
+-- migrations/         # DB migrations
+-- pipeline/           # Core pipeline code
|   +-- utilities/      # Maintenance scripts
+-- scrapers/           # Data source scrapers
+-- tests/              # Test suite
+-- wrappers/           # Entry point scripts
```

**Questions to answer:**
- Are files in the right directories?
- Should any directories be consolidated?
- Are there orphaned files at the root level?

### 6. Naming Consistency

**Check for:**
- Inconsistent casing (snake_case vs camelCase)
- Inconsistent prefixes (test_ vs check_ vs validate_)
- Abbreviated vs full names
- Plural vs singular directory names

### 7. Git Hygiene

```bash
# Check for large files that shouldn't be tracked
git ls-files | xargs ls -la 2>/dev/null | sort -k5 -n | tail -20

# Check for sensitive files
git ls-files | grep -E "\.env|secret|credential|key"

# Untracked files that might need attention
git status --porcelain | grep "^??"
```

## Output Format

Produce a structured report:

```markdown
## Repository Health Report

**Date:** [Date]
**Reviewer:** Claude (repo-reviewer skill)

### Summary

| Category | Issues Found | Severity |
|----------|--------------|----------|
| Documentation | X | High/Med/Low |
| Code Duplication | X | High/Med/Low |
| Dead Code | X | High/Med/Low |
| Config Sprawl | X | High/Med/Low |
| Structure | X | High/Med/Low |

### Critical Issues (Fix Now)

1. **[Issue]**
   - Location: [file path]
   - Problem: [description]
   - Suggested fix: [action]

### Recommended Cleanup (This Week)

1. **[Issue]**
   - Files affected: [list]
   - Action: [consolidate/delete/archive/move]

### Minor Items (Backlog)

1. [Item]
2. [Item]

### Files to Delete

```bash
# Run these commands to clean up:
rm [file1]
rm [file2]
git rm [file3]
```

### Files to Archive

```bash
# Move to archive:
mv docs/[old-file].md docs/archive/
```

### Consolidation Opportunities

| Files | Consolidate Into |
|-------|------------------|
| [file1], [file2] | [new-file] |
```

## Key Files to Review

- `CLAUDE.md` - Main project documentation (watch for drift)
- `docs/README.md` - Documentation index
- `docs/REPOSITORY_STRUCTURE.md` - Should match actual structure
- `pipeline/utilities/` - Backfill scripts lifecycle
- `docs/architecture/In Progress/` - Stale epics
- `docs/archive/` - Ensure archived items are truly archived

## Anti-Patterns to Flag

| Pattern | Problem | Solution |
|---------|---------|----------|
| `# TODO: ...` older than 30 days | Stale intent | Do it or delete it |
| `# HACK: ...` or `# FIXME: ...` | Technical debt | Track in issue |
| Commented-out code blocks | Noise | Delete (git has history) |
| `_old`, `_backup`, `_v2` suffixes | Versioning in filenames | Use git branches |
| Empty `__init__.py` with no imports | Unnecessary | Delete if not needed |
| Duplicate docstrings | Maintenance burden | Single source of truth |
