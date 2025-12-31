"""
Large-scale test for classifier summary retry logic.
Tests 10 diverse job descriptions to verify retry improves summary coverage.
"""
import sys
sys.path.insert(0, 'C:\\Cursor Projects\\job-analytics')

import time
from pipeline.classifier import classify_job


def run_large_test():
    print('='*70)
    print('LARGER TEST: Classifier Summary Retry Logic (10 jobs)')
    print('='*70)

    # Diverse test jobs to stress-test the classifier
    test_jobs = [
        {
            'title': 'Senior Data Engineer',
            'company': 'Stripe',
            'description': '''Senior Data Engineer at Stripe. Build scalable data pipelines
            using Python and Spark. Work with petabyte-scale datasets. Requirements: 5+ years
            Python, SQL, distributed systems experience.'''
        },
        {
            'title': 'Product Manager, Payments',
            'company': 'PayPal',
            'description': '''Lead product strategy for our payments platform. Define roadmap,
            work with engineering, analyze user data. Requirements: 4+ years PM experience,
            fintech background preferred.'''
        },
        {
            'title': 'Machine Learning Engineer',
            'company': 'OpenAI',
            'description': '''Build and deploy ML models at scale. Work on LLM infrastructure.
            Requirements: PhD or equivalent, PyTorch, distributed training experience.'''
        },
        {
            'title': 'Staff Software Engineer',
            'company': 'Google',
            'description': '''Design and implement large-scale distributed systems. Lead technical
            projects. Requirements: 8+ years experience, strong CS fundamentals.'''
        },
        {
            'title': 'Data Scientist',
            'company': 'Netflix',
            'description': '''Apply statistical methods to improve content recommendations.
            A/B testing, causal inference. Requirements: MS in Stats/CS, Python, SQL.'''
        },
        {
            'title': 'Engineering Manager',
            'company': 'Meta',
            'description': '''Lead a team of 8-10 engineers building infrastructure.
            Hire and develop talent. Requirements: 3+ years management, technical background.'''
        },
        {
            'title': 'Principal Product Manager',
            'company': 'Amazon',
            'description': '''Define product vision for AWS services. Work with executive team.
            Requirements: 10+ years product experience, cloud infrastructure knowledge.'''
        },
        {
            'title': 'Analytics Engineer',
            'company': 'dbt Labs',
            'description': '''Build data models and analytics infrastructure. dbt, SQL,
            data warehousing. Requirements: 3+ years analytics engineering.'''
        },
        {
            'title': 'Delivery Manager',
            'company': 'ThoughtWorks',
            'description': '''Lead agile delivery for client projects. Scrum, stakeholder
            management. Requirements: 5+ years delivery/project management.'''
        },
        {
            'title': 'VP of Engineering',
            'company': 'Startup Inc',
            'description': '''Build and scale engineering organization. Hire leaders,
            set technical direction. Requirements: 15+ years experience, startup experience.'''
        }
    ]

    # Track results
    results = {
        'total': len(test_jobs),
        'with_summary': 0,
        'without_summary': 0,
        'first_try': 0,
        'needed_retry': 0,
        'total_cost': 0.0,
        'total_latency': 0.0
    }

    print(f'\nProcessing {len(test_jobs)} test jobs...\n')
    print('-'*70)

    for i, job in enumerate(test_jobs, 1):
        try:
            result = classify_job(
                job_text=job['description'],
                verbose=False,
                structured_input=job
            )

            summary = result.get('summary', '')
            cost_data = result.get('_cost_data', {})
            attempts = cost_data.get('attempts', 1)
            cost = cost_data.get('total_cost', 0)
            latency = cost_data.get('latency_ms', 0)

            results['total_cost'] += cost
            results['total_latency'] += latency

            has_summary = bool(summary and len(summary.strip()) > 10)

            if has_summary:
                results['with_summary'] += 1
                if attempts == 1:
                    results['first_try'] += 1
                else:
                    results['needed_retry'] += 1
                status = 'OK'
            else:
                results['without_summary'] += 1
                status = 'MISSING'

            summary_preview = (summary[:50] + '...') if summary and len(summary) > 50 else (summary or 'N/A')
            print(f'[{i:2}/{len(test_jobs)}] {job["title"][:30]:30} | {status:7} | Attempts: {attempts} | {summary_preview}')

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        except Exception as e:
            print(f'[{i:2}/{len(test_jobs)}] {job["title"][:30]:30} | ERROR: {str(e)[:40]}')
            results['without_summary'] += 1

    print('-'*70)
    print('')
    print('='*70)
    print('RESULTS SUMMARY')
    print('='*70)
    print(f'')
    print(f'Jobs processed:     {results["total"]}')
    print(f'With summary:       {results["with_summary"]} ({results["with_summary"]/results["total"]*100:.1f}%)')
    print(f'Without summary:    {results["without_summary"]} ({results["without_summary"]/results["total"]*100:.1f}%)')
    print(f'')
    print(f'First try success:  {results["first_try"]}')
    print(f'Needed retry:       {results["needed_retry"]}')
    print(f'')
    print(f'Total cost:         ${results["total_cost"]:.4f}')
    print(f'Avg cost per job:   ${results["total_cost"]/results["total"]:.6f}')
    print(f'Total latency:      {results["total_latency"]/1000:.1f}s')
    print(f'Avg latency:        {results["total_latency"]/results["total"]:.0f}ms')
    print('='*70)

    return results['with_summary'] == results['total']


if __name__ == "__main__":
    success = run_large_test()
    exit(0 if success else 1)
