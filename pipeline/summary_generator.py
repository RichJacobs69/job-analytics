"""
Job Summary Generator (Backfill Utility)
Generates AI role summaries for jobs that don't have them.

Part of: EPIC-008 Curated Job Feed

NOTE: New jobs get summaries inline during classification (classifier.py).
This script is only for backfilling existing jobs or regenerating summaries.

Usage:
  python pipeline/summary_generator.py                  # Generate all missing
  python pipeline/summary_generator.py --limit=100      # Generate first 100
  python pipeline/summary_generator.py --dry-run        # Preview without updating
  python pipeline/summary_generator.py --verify         # Just check current state
"""

import sys
sys.path.insert(0, '.')

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

from pipeline.db_connection import supabase

# ============================================
# Gemini Configuration
# ============================================

import google.generativeai as genai

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in .env file")

genai.configure(api_key=GOOGLE_API_KEY)

gemini_model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
    generation_config={
        "temperature": 0.3,
        "max_output_tokens": 500,
        "response_mime_type": "application/json"
    }
)

# ============================================
# Prompt Template
# ============================================

SUMMARY_PROMPT = """You are a job description summarizer. Given a job posting, create a brief, informative summary.

JOB TITLE: {title}
COMPANY: {company}

JOB DESCRIPTION:
{description}

---

Generate a JSON response with:
"summary": A 2-3 sentence summary of the role. Focus on:
- What the person will do day-to-day
- Key responsibilities
- Team/product context if mentioned
Keep it concise and actionable. Avoid generic phrases like "exciting opportunity".

Response format:
{{"summary": "..."}}
"""


def generate_summary(title: str, company: str, description: str, max_retries: int = 3) -> Optional[Dict]:
    """
    Generate summary for a single job using Gemini.

    Returns:
        Dict with 'summary', or None on failure
    """
    # Truncate description if too long (Gemini has context limits)
    max_desc_length = 8000
    if len(description) > max_desc_length:
        description = description[:max_desc_length] + "..."

    prompt = SUMMARY_PROMPT.format(
        title=title,
        company=company,
        description=description
    )

    for attempt in range(max_retries):
        try:
            response = gemini_model.generate_content(prompt)
            result = json.loads(response.text)

            # Validate response structure
            if 'summary' not in result:
                return None

            return {
                'summary': result['summary']
            }

        except json.JSONDecodeError as e:
            print(f"   [WARN] JSON parse error: {e}")
            return None
        except Exception as e:
            error_str = str(e)
            if '429' in error_str and attempt < max_retries - 1:
                # Rate limited - exponential backoff
                wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                print(f"   [RATE LIMIT] Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                time.sleep(wait_time)
                continue
            else:
                print(f"   [WARN] Gemini API error: {e}")
                return None

    return None


def generate_summaries(batch_size: int = 50, limit: int = None, dry_run: bool = False):
    """
    Generate summaries for jobs that don't have them yet.
    Updates the enriched_jobs.summary column directly.

    Args:
        batch_size: How many jobs to process before pausing
        limit: Maximum jobs to process (None = all)
        dry_run: If True, show what would be generated without updating database
    """
    print("=" * 70)
    print("JOB SUMMARY GENERATOR (Backfill Utility)")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Batch size: {batch_size}")
    print(f"Limit: {limit or 'None (process all)'}")
    print(f"Dry run: {dry_run}")
    print()
    print("NOTE: New jobs get summaries inline during classification.")
    print("      This script is for backfilling existing jobs only.")
    print()

    # Step 1: Find jobs needing summaries (Greenhouse/Lever/Ashby with NULL summary)
    print("[DATA] Finding jobs without summaries...")

    try:
        jobs_to_process = []
        offset = 0
        page_size = 1000

        while True:
            # Query enriched_jobs where summary IS NULL
            result = supabase.table("enriched_jobs") \
                .select("id, raw_job_id, title_display, employer_name") \
                .in_("data_source", ["greenhouse", "lever", "ashby"]) \
                .is_("summary", "null") \
                .range(offset, offset + page_size - 1) \
                .execute()

            if not result.data:
                break

            jobs_to_process.extend(result.data)

            if len(result.data) < page_size:
                break
            offset += page_size

        print(f"[OK] Found {len(jobs_to_process)} jobs needing summaries")

        if not jobs_to_process:
            print("\n[DONE] All jobs already have summaries!")
            return

        # Apply limit if specified
        if limit:
            jobs_to_process = jobs_to_process[:limit]
            print(f"[LIMIT] Processing first {limit} jobs")

    except Exception as e:
        print(f"[ERROR] Failed to find jobs: {e}")
        return

    # Step 2: Fetch raw job descriptions
    print("\n[DATA] Fetching job descriptions...")

    raw_job_ids = [job['raw_job_id'] for job in jobs_to_process]
    raw_text_map = {}

    try:
        batch_fetch_size = 500
        for i in range(0, len(raw_job_ids), batch_fetch_size):
            batch_ids = raw_job_ids[i:i + batch_fetch_size]
            result = supabase.table("raw_jobs") \
                .select("id, raw_text") \
                .in_("id", batch_ids) \
                .execute()

            for row in result.data:
                raw_text_map[row['id']] = row.get('raw_text') or ''

        print(f"[OK] Retrieved descriptions for {len(raw_text_map)} jobs")

    except Exception as e:
        print(f"[ERROR] Failed to fetch descriptions: {e}")
        return

    # Step 3: Generate summaries
    print(f"\n[GENERATE] Generating summaries for {len(jobs_to_process)} jobs...")

    generated = 0
    skipped = 0
    errors = 0

    for i, job in enumerate(jobs_to_process, 1):
        enriched_job_id = job['id']
        raw_job_id = job['raw_job_id']
        title = job['title_display']
        company = job['employer_name']
        description = raw_text_map.get(raw_job_id, '')

        # Skip if no description
        if not description or len(description) < 100:
            print(f"   [SKIP] [{i}/{len(jobs_to_process)}] {title[:40]} - No description")
            skipped += 1
            continue

        # Generate summary
        print(f"   [GEN] [{i}/{len(jobs_to_process)}] {title[:40]} @ {company[:20]}...", end=" ")

        if dry_run:
            print("[DRY RUN]")
            generated += 1
            continue

        result = generate_summary(title, company, description)

        if result:
            # Update enriched_jobs.summary column directly
            try:
                supabase.table("enriched_jobs") \
                    .update({
                        'summary': result['summary'],
                        'summary_model': 'gemini-2.5-flash-lite'
                    }) \
                    .eq('id', enriched_job_id) \
                    .execute()

                print("OK")
                generated += 1

            except Exception as e:
                print(f"DB ERROR: {e}")
                errors += 1
        else:
            print("FAILED")
            errors += 1

        # Rate limiting
        if i % batch_size == 0:
            print(f"\n   [PAUSE] Processed {i} jobs, pausing 2s...")
            time.sleep(2)

        # Small delay between requests
        time.sleep(0.3)

    # Step 4: Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Jobs processed: {len(jobs_to_process)}")
    print(f"Summaries generated: {generated}")
    print(f"Skipped (no description): {skipped}")
    print(f"Errors: {errors}")

    print("\n[DONE] Summary generation complete!")


def verify_summaries():
    """Verify enriched_jobs.summary column contents."""
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    try:
        # Get counts by source
        for source in ['greenhouse', 'lever', 'ashby']:
            total = supabase.table("enriched_jobs") \
                .select("id", count='exact') \
                .eq("data_source", source) \
                .execute()

            with_summary = supabase.table("enriched_jobs") \
                .select("id", count='exact') \
                .eq("data_source", source) \
                .not_.is_("summary", "null") \
                .execute()

            pct = (with_summary.count / total.count * 100) if total.count > 0 else 0
            print(f"\n{source.capitalize():12} {with_summary.count:5} / {total.count:5} have summaries ({pct:.1f}%)")

        # Get recent samples
        result = supabase.table("enriched_jobs") \
            .select("title_display, employer_name, summary") \
            .not_.is_("summary", "null") \
            .order("classified_at", desc=True) \
            .limit(3) \
            .execute()

        if result.data:
            print("\n" + "-" * 70)
            print("Recent summaries:")
            print("-" * 70)

            for row in result.data:
                print(f"\n{row['title_display']} @ {row['employer_name']}")
                summary = row['summary'] or ''
                print(f"  {summary[:120]}...")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")


if __name__ == "__main__":
    import sys

    dry_run = "--dry-run" in sys.argv or "-d" in sys.argv
    verify_only = "--verify" in sys.argv or "-v" in sys.argv

    # Parse limit argument
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])

    if verify_only:
        verify_summaries()
    else:
        generate_summaries(batch_size=50, limit=limit, dry_run=dry_run)
        verify_summaries()

    print("\n" + "=" * 70)
    print("USAGE:")
    print("  python pipeline/summary_generator.py                  # Generate all missing")
    print("  python pipeline/summary_generator.py --limit=100      # Generate first 100")
    print("  python pipeline/summary_generator.py --dry-run        # Preview without updating")
    print("  python pipeline/summary_generator.py --verify         # Just check current state")
    print("=" * 70)
