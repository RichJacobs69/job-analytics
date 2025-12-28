"""
Evaluate Gemini 2.0 Flash for job classification.
Compares against Claude Haiku ground truth.

Usage:
    python tests/eval_gemini.py --sample 10      # Quick test
    python tests/eval_gemini.py --sample 50      # Medium test
    python tests/eval_gemini.py                  # Full dataset
"""
import argparse
import json
import os
import sys
import time
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import google.generativeai as genai

from pipeline.classifier import build_classification_prompt
from pipeline.job_family_mapper import get_correct_job_family

load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("[ERROR] Missing GOOGLE_API_KEY in .env file")
    print("Get one from: https://aistudio.google.com/app/apikey")
    sys.exit(1)

genai.configure(api_key=GOOGLE_API_KEY)

# Gemini 2.0 Flash pricing (per 1M tokens)
GEMINI_INPUT_PRICE = 0.10
GEMINI_OUTPUT_PRICE = 0.40


def adapt_prompt_for_gemini(prompt: str) -> str:
    """
    Modify the classification prompt for Gemini-specific requirements:
    1. Years-First seniority logic (more normalized across companies)
    2. Consistent null handling (use JSON null, not string "null")
    3. Reinforce Product Manager title -> product family rule
    """
    # ===========================================
    # 1. SENIORITY: Years-First Logic
    # ===========================================
    old_priority = """**Priority Order (FOLLOW THIS STRICTLY):**
- **Title is primary signal**: If title explicitly states level (Junior, Senior, Staff, Principal, Director), use that as primary classification
- **Years as secondary signal**: Use experience years only when title is ambiguous (e.g., 'Data Scientist' without level qualifier)
- **When both present**: If title and years conflict, prioritize title unless conflict is extreme (e.g., 'Junior' with 15 years)"""

    new_priority = """**Priority Order (FOLLOW THIS STRICTLY):**
- **Years of experience is PRIMARY signal**: Use explicitly stated years to determine seniority level
- **Title is SECONDARY signal**: Only use title (Senior, Staff, etc.) when years are NOT stated
- **When both present**: Prioritize years over title for normalized cross-company comparison
- **When neither present**: Return null for seniority"""

    prompt = prompt.replace(old_priority, new_priority)

    old_examples = """**Title Priority Examples (STUDY THESE):**
- 'Senior Data Scientist, 4 years' -> senior (title wins over years)
- 'Staff Engineer, 8 years' -> staff_principal (title wins)
- 'Director of Data, 7 years' -> director_plus (title wins)
- 'Data Scientist, 7 years' -> senior (years guide when no level in title)
- 'Lead Data Scientist' -> senior (Lead = senior level)
- 'Principal PM, 9 years' -> staff_principal (title wins despite years suggesting senior)"""

    new_examples = """**Seniority Examples (STUDY THESE - Years First):**
- 'Senior Data Scientist, 4 years' -> mid (4 years = mid, ignore title)
- 'Data Scientist, 7 years' -> senior (7 years = senior)
- 'Staff Engineer, 8 years' -> senior (8 years = senior, not staff_principal)
- 'Data Scientist, 12 years' -> staff_principal (12 years = staff_principal)
- 'Director of Data, 7 years' -> director_plus (Director title = management track)
- 'Senior Data Scientist' (no years stated) -> senior (fall back to title)
- 'Data Scientist' (no years, no level) -> null (insufficient signal)"""

    prompt = prompt.replace(old_examples, new_examples)

    # ===========================================
    # 2. NULL HANDLING & PRODUCT MANAGER RULE
    # ===========================================
    # Add instructions before the output schema section
    extra_instructions = """
**CRITICAL RULES - READ BEFORE CLASSIFYING:**

1. **NULL VALUES**: When a field is unknown or not stated, use JSON null (not the string "null").
   - Correct: "seniority": null
   - Wrong: "seniority": "null"

2. **PRODUCT MANAGER TITLE RULE**: If the job title contains "Product Manager", "PM", or "GPM",
   it is ALWAYS a product subfamily, regardless of any qualifier words like "Data", "Technical", "Growth".
   - "Data Product Manager" -> job_subfamily: core_pm (NOT data family)
   - "Senior Data Product Manager, GTM" -> job_subfamily: core_pm
   - "Technical Product Manager" -> job_subfamily: technical_pm
   - "Growth PM" -> job_subfamily: growth_pm
   - "AI/ML PM" -> job_subfamily: ai_ml_pm
   - "Product Manager" (generic) -> job_subfamily: core_pm
   The word "Product Manager" in the title is the deciding factor.

   IMPORTANT: Use ONLY these exact product subfamily codes: core_pm, platform_pm, technical_pm, growth_pm, ai_ml_pm
   Do NOT invent new codes like "product_pm" - use "core_pm" for general PM roles.

"""
    prompt = prompt.replace(
        "# REQUIRED OUTPUT SCHEMA",
        extra_instructions + "# REQUIRED OUTPUT SCHEMA"
    )

    return prompt


def classify_with_gemini(job_text: str, verbose: bool = False) -> Dict:
    """
    Classify a job using Gemini 2.0 Flash.
    Uses adapted prompt with Years-First seniority logic.
    """
    prompt = build_classification_prompt(job_text)
    prompt = adapt_prompt_for_gemini(prompt)

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={
            "temperature": 0.1,
            "max_output_tokens": 4000,  # Increased to avoid truncation
            "response_mime_type": "application/json"
        }
    )

    start_time = time.time()

    try:
        response = model.generate_content(prompt)
        latency_ms = (time.time() - start_time) * 1000

        # Extract token counts
        # Gemini reports usage_metadata with prompt_token_count and candidates_token_count
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0

        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * GEMINI_INPUT_PRICE
        output_cost = (output_tokens / 1_000_000) * GEMINI_OUTPUT_PRICE
        total_cost = input_cost + output_cost

        # Parse JSON response
        response_text = response.text.strip()

        # Clean up any markdown fences
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        result = json.loads(response_text)

        # Handle list responses (Gemini sometimes returns array for malformed input)
        if isinstance(result, list):
            if len(result) > 0 and isinstance(result[0], dict):
                result = result[0]  # Take first item
            else:
                raise ValueError(f"Expected dict, got empty or invalid list")

        # Validate result structure
        if not isinstance(result, dict):
            raise ValueError(f"Expected dict, got {type(result).__name__}")

        # Auto-derive job_family from job_subfamily (same as Claude)
        role = result.get('role', {})
        if isinstance(role, dict) and role.get('job_subfamily'):
            job_subfamily = role['job_subfamily']
            if job_subfamily == 'out_of_scope':
                result['role']['job_family'] = 'out_of_scope'
            else:
                result['role']['job_family'] = get_correct_job_family(job_subfamily)

        result['_cost_data'] = {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_cost': total_cost,
            'latency_ms': latency_ms
        }

        return result

    except json.JSONDecodeError as e:
        return {
            '_error': f"JSON parse error: {e}",
            '_raw_response': response_text if 'response_text' in locals() else None,
            '_cost_data': {'input_tokens': 0, 'output_tokens': 0, 'total_cost': 0}
        }
    except Exception as e:
        return {
            '_error': str(e),
            '_cost_data': {'input_tokens': 0, 'output_tokens': 0, 'total_cost': 0}
        }


def evaluate_gemini(dataset_path: str, sample_size: int = None, verbose: bool = False):
    """
    Run Gemini evaluation on test dataset.
    """
    print(f"\n{'='*60}")
    print("GEMINI 2.0 FLASH EVALUATION")
    print(f"{'='*60}\n")

    # Load dataset
    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    jobs = dataset['jobs']
    if sample_size:
        jobs = jobs[:sample_size]

    print(f"Evaluating {len(jobs)} jobs from {dataset_path}")
    print(f"Ground truth from Claude Haiku classifications\n")

    # Results tracking
    results = {
        'total': len(jobs),
        'json_success': 0,
        'errors': [],
        'costs': [],
        'latencies': [],
        'field_matches': {
            'job_family': {'match': 0, 'mismatch': 0, 'details': []},
            'job_subfamily': {'match': 0, 'mismatch': 0, 'details': []},
            'seniority': {'match': 0, 'mismatch': 0, 'details': []},
            'working_arrangement': {'match': 0, 'mismatch': 0, 'details': []}
        }
    }

    for i, job in enumerate(jobs, 1):
        title = job['title'][:50] if job.get('title') else 'Unknown'
        print(f"[{i}/{len(jobs)}] {title}...", end=" ", flush=True)

        # Classify with Gemini
        gemini_result = classify_with_gemini(job['raw_text'], verbose=verbose)

        if '_error' in gemini_result:
            print(f"ERROR: {gemini_result['_error'][:50]}")
            results['errors'].append({
                'job_id': job['id'],
                'title': title,
                'error': gemini_result['_error']
            })
            continue

        results['json_success'] += 1

        cost_data = gemini_result.get('_cost_data', {})
        results['costs'].append(cost_data.get('total_cost', 0))
        results['latencies'].append(cost_data.get('latency_ms', 0))

        # Compare fields against ground truth
        ground_truth = job['ground_truth']
        gemini_role = gemini_result.get('role', {})
        gemini_location = gemini_result.get('location', {})

        # job_family comparison
        gt_family = ground_truth.get('job_family')
        gemini_family = gemini_role.get('job_family')
        if gt_family == gemini_family:
            results['field_matches']['job_family']['match'] += 1
        else:
            results['field_matches']['job_family']['mismatch'] += 1
            results['field_matches']['job_family']['details'].append({
                'title': title,
                'ground_truth': gt_family,
                'gemini': gemini_family
            })

        # job_subfamily comparison
        gt_subfamily = ground_truth.get('job_subfamily')
        gemini_subfamily = gemini_role.get('job_subfamily')
        if gt_subfamily == gemini_subfamily:
            results['field_matches']['job_subfamily']['match'] += 1
        else:
            results['field_matches']['job_subfamily']['mismatch'] += 1
            results['field_matches']['job_subfamily']['details'].append({
                'title': title,
                'ground_truth': gt_subfamily,
                'gemini': gemini_subfamily
            })

        # seniority comparison
        gt_seniority = ground_truth.get('seniority')
        gemini_seniority = gemini_role.get('seniority')
        if gt_seniority == gemini_seniority:
            results['field_matches']['seniority']['match'] += 1
        else:
            results['field_matches']['seniority']['mismatch'] += 1
            results['field_matches']['seniority']['details'].append({
                'title': title,
                'ground_truth': gt_seniority,
                'gemini': gemini_seniority
            })

        # working_arrangement comparison
        gt_arrangement = ground_truth.get('working_arrangement')
        gemini_arrangement = gemini_location.get('working_arrangement')
        if gt_arrangement == gemini_arrangement:
            results['field_matches']['working_arrangement']['match'] += 1
        else:
            results['field_matches']['working_arrangement']['mismatch'] += 1
            results['field_matches']['working_arrangement']['details'].append({
                'title': title,
                'ground_truth': gt_arrangement,
                'gemini': gemini_arrangement
            })

        cost = cost_data.get('total_cost', 0)
        latency = cost_data.get('latency_ms', 0)
        print(f"OK (${cost:.5f}, {latency:.0f}ms)")

        # Rate limiting - Gemini has generous limits but be safe
        time.sleep(0.5)

    # Print results
    print(f"\n{'='*60}")
    print("EVALUATION RESULTS")
    print(f"{'='*60}")

    print(f"\nJSON Parse Success: {results['json_success']}/{results['total']} ({100*results['json_success']/results['total']:.1f}%)")
    print(f"Errors: {len(results['errors'])}")

    if results['costs']:
        avg_cost = sum(results['costs']) / len(results['costs'])
        total_cost = sum(results['costs'])
        print(f"\nCost:")
        print(f"  Average per job: ${avg_cost:.5f}")
        print(f"  Total for evaluation: ${total_cost:.4f}")

    if results['latencies']:
        avg_latency = sum(results['latencies']) / len(results['latencies'])
        p95_latency = sorted(results['latencies'])[int(len(results['latencies']) * 0.95)] if len(results['latencies']) > 20 else max(results['latencies'])
        print(f"\nLatency:")
        print(f"  Average: {avg_latency:.0f}ms")
        print(f"  P95: {p95_latency:.0f}ms")

    print(f"\n{'='*60}")
    print("FIELD ACCURACY (vs Claude Ground Truth)")
    print(f"{'='*60}")

    for field, data in results['field_matches'].items():
        total = data['match'] + data['mismatch']
        if total > 0:
            accuracy = 100 * data['match'] / total
            print(f"\n{field}:")
            print(f"  Accuracy: {data['match']}/{total} ({accuracy:.1f}%)")

            # Show mismatches if any
            if data['details'] and len(data['details']) <= 10:
                print(f"  Mismatches:")
                for d in data['details'][:5]:
                    print(f"    - {d['title'][:40]}: {d['ground_truth']} -> {d['gemini']}")

    # Save detailed results
    output_path = 'tests/fixtures/gemini_eval_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {output_path}")

    # Summary recommendation
    print(f"\n{'='*60}")
    print("RECOMMENDATION")
    print(f"{'='*60}")

    family_acc = 100 * results['field_matches']['job_family']['match'] / (results['field_matches']['job_family']['match'] + results['field_matches']['job_family']['mismatch']) if (results['field_matches']['job_family']['match'] + results['field_matches']['job_family']['mismatch']) > 0 else 0
    subfamily_acc = 100 * results['field_matches']['job_subfamily']['match'] / (results['field_matches']['job_subfamily']['match'] + results['field_matches']['job_subfamily']['mismatch']) if (results['field_matches']['job_subfamily']['match'] + results['field_matches']['job_subfamily']['mismatch']) > 0 else 0

    if family_acc >= 95 and subfamily_acc >= 90:
        print("\n[GO] Gemini 2.0 Flash meets accuracy thresholds!")
        print(f"  - job_family: {family_acc:.1f}% (threshold: 95%)")
        print(f"  - job_subfamily: {subfamily_acc:.1f}% (threshold: 90%)")
        print(f"  - Cost savings: ~90%")
    else:
        print("\n[REVIEW NEEDED] Accuracy below thresholds")
        print(f"  - job_family: {family_acc:.1f}% (threshold: 95%)")
        print(f"  - job_subfamily: {subfamily_acc:.1f}% (threshold: 90%)")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Gemini 2.0 Flash")
    parser.add_argument('--sample', type=int, default=None, help='Number of jobs to test')
    parser.add_argument('--dataset', type=str, default='tests/fixtures/llm_eval_dataset.json', help='Dataset path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()
    evaluate_gemini(args.dataset, sample_size=args.sample, verbose=args.verbose)
