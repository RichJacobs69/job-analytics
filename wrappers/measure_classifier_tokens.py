"""
Measure actual token usage from classifier.
Run on sample jobs to get accurate averages for cost comparison.

Usage:
    python wrappers/measure_classifier_tokens.py --sample 20
    python wrappers/measure_classifier_tokens.py --sample 50 --verbose
"""
import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.db_connection import supabase
from pipeline.classifier import classify_job_with_claude


def measure_token_usage(sample_size: int = 20, verbose: bool = False):
    """
    Measure token usage across sample of recent classified jobs.

    Args:
        sample_size: Number of jobs to sample (default 20)
        verbose: Print per-job details
    """
    print(f"\n{'='*60}")
    print(f"MEASURING CLASSIFIER TOKEN USAGE")
    print(f"Sample size: {sample_size} jobs")
    print(f"{'='*60}\n")

    # Fetch recent jobs that have raw_text available
    # Using raw_jobs table which has the original job text
    print("Fetching sample jobs from database...")

    response = supabase.table('raw_jobs').select(
        'id, title, company, raw_text, source'
    ).not_.is_('raw_text', 'null').order('scraped_at', desc=True).limit(sample_size * 2).execute()

    if not response.data:
        print("[ERROR] No jobs found with raw_text")
        return

    jobs = response.data[:sample_size]
    print(f"Found {len(jobs)} jobs to process\n")

    # Track stats
    stats = {
        'input_tokens': [],
        'output_tokens': [],
        'total_costs': [],
        'sources': {'greenhouse': [], 'lever': [], 'adzuna': []}
    }

    for i, job in enumerate(jobs, 1):
        job_id = job['id']
        title = job.get('title', 'Unknown')[:50]
        source = job.get('source', 'unknown')

        if verbose:
            print(f"[{i}/{len(jobs)}] Processing: {title}...")

        try:
            # Re-classify to measure tokens (not saving, just measuring)
            result = classify_job_with_claude(job['raw_text'], verbose=False)

            cost_data = result.get('_cost_data', {})
            input_tokens = cost_data.get('input_tokens', 0)
            output_tokens = cost_data.get('output_tokens', 0)
            total_cost = cost_data.get('total_cost', 0)

            stats['input_tokens'].append(input_tokens)
            stats['output_tokens'].append(output_tokens)
            stats['total_costs'].append(total_cost)

            if source in stats['sources']:
                stats['sources'][source].append({
                    'input': input_tokens,
                    'output': output_tokens
                })

            if verbose:
                print(f"   Input: {input_tokens:,} | Output: {output_tokens:,} | Cost: ${total_cost:.5f}")

        except Exception as e:
            print(f"   [ERROR] Failed: {e}")
            continue

    # Calculate averages
    if not stats['input_tokens']:
        print("\n[ERROR] No successful classifications")
        return

    avg_input = sum(stats['input_tokens']) / len(stats['input_tokens'])
    avg_output = sum(stats['output_tokens']) / len(stats['output_tokens'])
    avg_cost = sum(stats['total_costs']) / len(stats['total_costs'])

    min_input = min(stats['input_tokens'])
    max_input = max(stats['input_tokens'])
    min_output = min(stats['output_tokens'])
    max_output = max(stats['output_tokens'])

    print(f"\n{'='*60}")
    print("TOKEN USAGE SUMMARY")
    print(f"{'='*60}")
    print(f"Jobs processed: {len(stats['input_tokens'])}")
    print(f"\nInput Tokens:")
    print(f"  Average: {avg_input:,.0f}")
    print(f"  Min: {min_input:,} | Max: {max_input:,}")
    print(f"\nOutput Tokens:")
    print(f"  Average: {avg_output:,.0f}")
    print(f"  Min: {min_output:,} | Max: {max_output:,}")
    print(f"\nCurrent Cost (Claude Haiku at code prices):")
    print(f"  Average per job: ${avg_cost:.5f}")

    # Cost projections with VERIFIED pricing
    print(f"\n{'='*60}")
    print("COST PROJECTIONS (using verified Dec 2025 pricing)")
    print(f"{'='*60}")

    providers = {
        'Claude 3.5 Haiku': {'input': 1.00, 'output': 5.00},
        'Gemini 2.0 Flash': {'input': 0.10, 'output': 0.40},
        'DeepSeek V3.2 (miss)': {'input': 0.28, 'output': 0.42},
        'DeepSeek V3.2 (hit)': {'input': 0.028, 'output': 0.42},
        'Groq Llama 4 Scout': {'input': 0.11, 'output': 0.34},
    }

    print(f"\nBased on avg {avg_input:,.0f} input / {avg_output:,.0f} output tokens:\n")

    baseline_cost = None
    for name, prices in providers.items():
        cost = (avg_input / 1_000_000) * prices['input'] + (avg_output / 1_000_000) * prices['output']
        if baseline_cost is None:
            baseline_cost = cost
            savings = "-"
        else:
            savings = f"{((baseline_cost - cost) / baseline_cost) * 100:.0f}%"
        print(f"  {name:25} ${cost:.5f}/job  (savings: {savings})")

    # Per-source breakdown if available
    print(f"\n{'='*60}")
    print("BY SOURCE")
    print(f"{'='*60}")
    for source, data in stats['sources'].items():
        if data:
            src_avg_input = sum(d['input'] for d in data) / len(data)
            src_avg_output = sum(d['output'] for d in data) / len(data)
            print(f"\n{source.capitalize()} ({len(data)} jobs):")
            print(f"  Avg input: {src_avg_input:,.0f} | Avg output: {src_avg_output:,.0f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measure classifier token usage")
    parser.add_argument('--sample', type=int, default=20, help='Number of jobs to sample')
    parser.add_argument('--verbose', '-v', action='store_true', help='Print per-job details')

    args = parser.parse_args()
    measure_token_usage(sample_size=args.sample, verbose=args.verbose)
