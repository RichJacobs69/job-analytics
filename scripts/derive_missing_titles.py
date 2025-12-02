"""
Script to derive job titles from raw_text for records with Unknown Title.

Reads raw_job_ids from a CSV file and fetches the raw_text from raw_jobs table,
then attempts to extract the job title from the description using:
1. Regex pattern matching for common title formats
2. Claude LLM extraction for complex cases

Usage:
    python scripts/derive_missing_titles.py [--use-llm] [--update-db]
"""
import os
import sys
import csv
import json
import re
import argparse
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.db_connection import supabase


def get_raw_jobs_by_ids(raw_job_ids: List[int]) -> Dict[int, Dict]:
    """
    Fetch raw jobs by their IDs.
    
    Args:
        raw_job_ids: List of raw_job_id values
        
    Returns:
        Dict mapping raw_job_id to raw job record
    """
    results = {}
    
    # Fetch in batches to avoid hitting query limits
    batch_size = 50
    for i in range(0, len(raw_job_ids), batch_size):
        batch = raw_job_ids[i:i + batch_size]
        
        try:
            response = supabase.table("raw_jobs").select("*").in_("id", batch).execute()
            for record in response.data:
                results[record["id"]] = record
        except Exception as e:
            print(f"Error fetching batch {i}: {e}")
    
    return results


# Common title patterns that indicate job roles
TITLE_PATTERNS = [
    # Director/Manager patterns
    r'((?:Senior\s+|Principal\s+|Lead\s+|Staff\s+)?Director[,\s]+\w+[\w\s,/&-]{5,60})',
    r'((?:Senior\s+|Principal\s+|Lead\s+|Staff\s+)?Manager[,\s]+\w+[\w\s,/&-]{5,60})',
    
    # Engineer patterns
    r'((?:Senior\s+|Principal\s+|Lead\s+|Staff\s+|Distinguished\s+)?(?:Data\s+)?Engineer[\w\s,/&()-]{0,40})',
    r'((?:Senior\s+|Principal\s+|Lead\s+|Staff\s+)?(?:ML|Machine Learning|AI|Software|Backend|Platform)\s+Engineer[\w\s,/&()-]{0,40})',
    
    # Data/Analytics patterns
    r'((?:Senior\s+|Principal\s+|Lead\s+|Staff\s+)?Data\s+(?:Scientist|Analyst|Architect)[\w\s,/&()-]{0,40})',
    r'((?:Senior\s+|Principal\s+|Lead\s+|Staff\s+)?Analytics\s+Engineer[\w\s,/&()-]{0,40})',
    
    # Product Manager patterns
    r'((?:Senior\s+|Principal\s+|Lead\s+|Staff\s+)?(?:Technical\s+)?Product\s+Manager[\w\s,/&()-]{0,50})',
    r'((?:Senior\s+|Principal\s+|Lead\s+|Staff\s+)?(?:TPM|PM)[\w\s,/&()-]{0,50})',
    r'((?:Senior\s+|Principal\s+)?(?:AI|ML|Data|Growth|Platform)\s+(?:PM|Product\s+Manager)[\w\s,/&()-]{0,40})',
    
    # Program Manager patterns  
    r'((?:Senior\s+|Principal\s+|Director[,\s]+)?(?:Technical\s+)?Program\s+Manag(?:er|ement)[\w\s,/&()-]{0,50})',
]

# Patterns that indicate start of job title section
JOB_TITLE_MARKERS = [
    r'Job\s+(?:Title|Description)[\s:]+([A-Z][\w\s,/&()-]{10,80}?)(?:\s+(?:About|Location|We|Our|At\s+))',
    r'The\s+Role[\s:]+([A-Z][\w\s,/&()-]{10,80})',
    r'Position[\s:]+([A-Z][\w\s,/&()-]{10,80})',
]


def extract_title_from_raw_text(raw_text: str, metadata: Optional[Dict] = None, employer: str = "") -> Tuple[Optional[str], str]:
    """
    Attempt to extract job title from raw_text or metadata.
    
    Args:
        raw_text: The raw job description text
        metadata: Optional metadata dict that may contain title info
        employer: Employer name (helps with extraction)
        
    Returns:
        Tuple of (extracted title or None, extraction method)
    """
    # First check metadata for title
    if metadata:
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                pass
        
        if isinstance(metadata, dict):
            # Check common title fields in metadata
            for key in ['title', 'job_title', 'position', 'role', 'Title']:
                if key in metadata and metadata[key]:
                    return str(metadata[key]).strip(), "metadata"
    
    # Try to extract from raw_text
    if not raw_text:
        return None, "no_text"
    
    # Clean up the text
    text = raw_text.strip()
    
    # Method 1: Check if title is at the very start (before company info)
    first_100 = text[:150]
    
    # Look for title patterns at the start
    for pattern in TITLE_PATTERNS:
        match = re.search(pattern, first_100, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean up trailing characters
            title = re.sub(r'\s+(Are|We|At|About|The|Our|Ever|Founded|Location).*$', '', title, flags=re.IGNORECASE)
            title = title.strip(' -,.')
            if len(title) > 10 and len(title) < 100:
                return title, "pattern_start"
    
    # Method 2: Look for job title markers
    for marker_pattern in JOB_TITLE_MARKERS:
        match = re.search(marker_pattern, text[:500], re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            title = title.strip(' -,.')
            if len(title) > 10 and len(title) < 100:
                return title, "marker"
    
    # Method 3: Search entire text for title patterns (some have title after company description)
    for pattern in TITLE_PATTERNS:
        match = re.search(pattern, text[:2000], re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean up
            title = re.sub(r'\s+(Are|We|At|About|The|Our|Ever|Founded|Location|Join|Apply).*$', '', title, flags=re.IGNORECASE)
            title = title.strip(' -,.')
            if len(title) > 10 and len(title) < 100:
                return title, "pattern_body"
    
    # Method 4: Check for "Job Description [Title]" pattern
    jd_match = re.search(r'Job\s+Description\s+([A-Z][^.]{10,80}?)(?:\s+(?:Ever|About|We|At\s+|Location))', text[:500], re.IGNORECASE)
    if jd_match:
        title = jd_match.group(1).strip()
        if len(title) > 10:
            return title, "jd_prefix"
    
    # Method 5: Look for specific role mentions
    role_patterns = [
        r'seeking\s+(?:a|an)\s+([\w\s,/&()-]{10,60}?)(?:\s+to|\.|who)',
        r'hiring\s+(?:a|an)\s+([\w\s,/&()-]{10,60}?)(?:\s+to|\.|who)',
        r'looking\s+for\s+(?:a|an)?\s*([\w\s,/&()-]{10,60}?)(?:\s+to|\.|who)',
    ]
    for pattern in role_patterns:
        match = re.search(pattern, text[:1500], re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            if any(keyword in title.lower() for keyword in ['engineer', 'manager', 'director', 'analyst', 'scientist', 'architect']):
                return title, "seeking_pattern"
    
    return None, "no_match"


def extract_title_with_llm(raw_text: str, employer: str) -> Tuple[Optional[str], str]:
    """
    Use Claude to extract job title from description text.
    
    Args:
        raw_text: The raw job description text
        employer: Employer name for context
        
    Returns:
        Tuple of (extracted title or None, extraction method)
    """
    if not raw_text or len(raw_text) < 50:
        return None, "insufficient_text"
    
    try:
        import anthropic
        from dotenv import load_dotenv
        load_dotenv()
        
        client = anthropic.Anthropic()
        
        # Truncate to first 2000 chars to save tokens
        text_sample = raw_text[:2000]
        
        prompt = f"""Extract the job title from this job posting description.

Company: {employer}

Job Description:
{text_sample}

Instructions:
- Return ONLY the job title, nothing else
- If multiple titles are mentioned, return the primary/main one
- Use standard title format (e.g., "Senior Data Engineer", "Product Manager", "ML Engineer")
- If you cannot determine a clear job title, return "UNKNOWN"
- Do not include company name in the title
- Do not include location in the title

Job Title:"""

        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )
        
        title = response.content[0].text.strip()
        
        # Validate the response
        if title and title != "UNKNOWN" and len(title) < 100:
            return title, "llm_extraction"
        else:
            return None, "llm_unknown"
            
    except Exception as e:
        print(f"LLM extraction error: {e}")
        return None, f"llm_error: {str(e)}"


def update_enriched_job_title(enriched_id: int, new_title: str) -> bool:
    """
    Update the title_display field in enriched_jobs table.
    
    Args:
        enriched_id: ID of the enriched_jobs record
        new_title: New title to set
        
    Returns:
        True if update was successful
    """
    try:
        result = supabase.table("enriched_jobs").update({
            "title_display": new_title
        }).eq("id", enriched_id).execute()
        
        return len(result.data) > 0
    except Exception as e:
        print(f"Error updating enriched job {enriched_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Derive job titles for records with Unknown Title'
    )
    parser.add_argument(
        '--use-llm',
        action='store_true',
        help='Use Claude LLM to extract titles that regex cannot find'
    )
    parser.add_argument(
        '--update-db',
        action='store_true',
        help='Update the database with derived titles'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes (implies --update-db)'
    )
    args = parser.parse_args()
    
    # Read the CSV file
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "Supabase Snippet Agency Flag and Confidence Summary (3).csv"
    )
    
    print(f"Reading CSV from: {csv_path}")
    print(f"Options: use_llm={args.use_llm}, update_db={args.update_db}, dry_run={args.dry_run}")
    print()
    
    records = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    
    print(f"Found {len(records)} records with Unknown Title")
    
    # Extract raw_job_ids
    raw_job_ids = [int(row['raw_job_id']) for row in records]
    
    print(f"Fetching raw_jobs for {len(raw_job_ids)} IDs...")
    
    # Fetch raw jobs
    raw_jobs = get_raw_jobs_by_ids(raw_job_ids)
    
    print(f"Retrieved {len(raw_jobs)} raw job records")
    print()
    
    # Process each record and try to derive title
    results = []
    llm_calls = 0
    
    for row in records:
        raw_job_id = int(row['raw_job_id'])
        employer = row['employer_name']
        enriched_id = row['id']
        
        raw_job = raw_jobs.get(raw_job_id)
        
        if not raw_job:
            print(f"[MISSING] raw_job_id {raw_job_id} not found in database")
            results.append({
                'enriched_id': enriched_id,
                'raw_job_id': raw_job_id,
                'employer': employer,
                'status': 'raw_job_not_found',
                'raw_text_preview': None,
                'derived_title': None,
                'extraction_method': None
            })
            continue
        
        raw_text = raw_job.get('raw_text', '')
        metadata = raw_job.get('metadata', {})
        full_text = raw_job.get('full_text', '')
        posting_url = raw_job.get('posting_url', '')
        
        # Use full text if available, otherwise raw_text
        text_to_analyze = full_text if full_text else raw_text
        
        # Show what we have
        text_preview = (text_to_analyze[:800] if text_to_analyze else 'N/A')
        
        print(f"=" * 80)
        print(f"Enriched ID: {enriched_id} | Raw Job ID: {raw_job_id} | Employer: {employer}")
        if posting_url:
            print(f"URL: {posting_url[:100]}...")
        print(f"-" * 80)
        print(f"TEXT ({len(text_to_analyze) if text_to_analyze else 0} chars):")
        print(text_preview)
        if text_to_analyze and len(text_to_analyze) > 800:
            print(f"... [truncated, {len(text_to_analyze) - 800} more chars]")
        print()
        
        # Try to derive title with regex first
        derived_title, method = extract_title_from_raw_text(text_to_analyze, metadata, employer)
        
        # Filter out false positives from regex
        if derived_title:
            # Check for known false positives
            false_positive_patterns = [
                r'^(Job\s+Description|Company\s+Description|About\s+Us|Overview)',
                r'^(Provide|Join|Our|The|We|At\s+)',
                r'toolkit|design|security',
            ]
            is_false_positive = False
            for pattern in false_positive_patterns:
                if re.search(pattern, derived_title, re.IGNORECASE):
                    is_false_positive = True
                    break
            
            if is_false_positive:
                print(f">>> Regex found '{derived_title}' but looks like a false positive")
                derived_title = None
                method = "false_positive_filtered"
        
        # If regex didn't find a title and --use-llm is set, try LLM
        if not derived_title and args.use_llm and text_to_analyze:
            print(f">>> Trying LLM extraction...")
            llm_calls += 1
            derived_title, method = extract_title_with_llm(text_to_analyze, employer)
        
        if derived_title:
            print(f">>> DERIVED TITLE: {derived_title}")
            print(f"    Method: {method}")
        else:
            print(f">>> Could not derive title (method: {method})")
        
        print()
        
        results.append({
            'enriched_id': enriched_id,
            'raw_job_id': raw_job_id,
            'employer': employer,
            'status': 'processed',
            'posting_url': posting_url,
            'raw_text_preview': text_preview,
            'full_text_length': len(text_to_analyze) if text_to_analyze else 0,
            'derived_title': derived_title,
            'extraction_method': method,
            'metadata': metadata
        })
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    derived_count = sum(1 for r in results if r.get('derived_title'))
    print(f"Total records: {len(results)}")
    print(f"Titles derived: {derived_count}")
    print(f"Could not derive: {len(results) - derived_count}")
    if args.use_llm:
        print(f"LLM calls made: {llm_calls}")
    
    # Group by extraction method
    methods = {}
    for r in results:
        method = r.get('extraction_method', 'unknown')
        methods[method] = methods.get(method, 0) + 1
    
    print("\nBy extraction method:")
    for method, count in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"  {method}: {count}")
    
    # Show successfully derived titles
    print("\n" + "=" * 80)
    print("DERIVED TITLES")
    print("=" * 80)
    for r in results:
        if r.get('derived_title'):
            print(f"  [{r['enriched_id']}] {r['employer']}: {r['derived_title']}")
    
    # Update database if requested
    if args.update_db or args.dry_run:
        print("\n" + "=" * 80)
        print("DATABASE UPDATES" + (" (DRY RUN)" if args.dry_run else ""))
        print("=" * 80)
        
        update_count = 0
        for r in results:
            if r.get('derived_title'):
                enriched_id = int(r['enriched_id'])
                new_title = r['derived_title']
                
                if args.dry_run:
                    print(f"  [DRY RUN] Would update ID {enriched_id}: '{new_title}'")
                    update_count += 1
                else:
                    success = update_enriched_job_title(enriched_id, new_title)
                    if success:
                        print(f"  [UPDATED] ID {enriched_id}: '{new_title}'")
                        update_count += 1
                    else:
                        print(f"  [FAILED] ID {enriched_id}")
        
        print(f"\nTotal {'would update' if args.dry_run else 'updated'}: {update_count}")
    
    # Show those that need manual review
    print("\n" + "=" * 80)
    print("NEED MANUAL REVIEW (could not derive)")
    print("=" * 80)
    for r in results:
        if not r.get('derived_title'):
            preview = r.get('raw_text_preview', '')[:200] if r.get('raw_text_preview') else 'N/A'
            print(f"  [{r['enriched_id']}] {r['employer']}:")
            print(f"    Preview: {preview}...")
            print()
    
    # Output results to JSON for further analysis
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "output",
        "title_derivation_results.json"
    )
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    main()

