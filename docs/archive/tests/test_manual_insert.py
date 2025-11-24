"""
Manual test: Insert ground truth jobs and validate classification
"""
import json
from datetime import date
from db_connection import insert_raw_job, insert_enriched_job, supabase, test_connection
from classifier import classify_job_with_claude

# ============================================
# Test Cases - YOUR GROUND TRUTH JOBS
# ============================================

TEST_JOBS = [
    {
        "source": "manual",
        "url": "https://www.linkedin.com/jobs/view/staff-data-engineer-kharon-denver",
        "posted_date": date(2025, 11, 10),
        "last_seen_date": date(2025, 11, 11),
        "raw_text": """
Staff Data Engineer
Kharon · Denver, CO (On-site) · 1 day ago
$230,000 - $280,000/yr · Full-time · On-site (4 days/week required)

About the job:
Kharon is seeking a full-time Staff Data Engineer to join our team in Denver, CO. This role requires in-office attendance at least 4 days a week.

RESPONSIBILITIES:
- Design and help build large-scale distributed automated data processing systems and data lakes, while optimizing for both computational and storage efficiency on AWS Databricks.
- Design and create batch and realtime data pipelines, infrastructure, and overall workflow orchestration to pull data from a diverse set of data sources into the Kharon Data Lake.
- Design and build systems to track, monitor and validate the quality of data coming into or going out of Kharon Data Lake.
- Collaborate with engineering, architects, data science, and product teams to ensure data architecture aligns with strategic goals and operational needs.
- Lead the adoption and integration of LLM-related tooling and vector databases into Kharon's data platform.
- Define and champion best practices in data modeling, ETL, data governance, and system design.
- Mentor engineers in data engineering principles, architecture design, and technical decision-making.

QUALIFICATIONS:
- Bachelor's degree in Computer Science, Engineering, or a related field preferred.
- 9-12+ years of experience in software or data engineering, with 4+ years in a senior or staff-level technical leadership role.
- Deep expertise in building scalable data architectures and distributed data systems.
- Proven track record of leading technical teams, providing mentorship, and fostering professional growth among engineers.
- Strong programming skills in Python, SQL, PySpark, and Notebooks.
- Hands-on experience with cloud based infrastructure like AWS, GCP, or Azure.
- Strong background in data warehousing and lakebase technologies such as Databricks, Snowflake, ClickHouse, or Athena.
- Proven ability to collaborate across functions and translate complex requirements into scalable technical solutions.
- Strong verbal and written communication skills.

NICE TO HAVE:
- Experience with LLM tools and vector databases (e.g., Langchain, FAISS, Pinecone).
- Experience working with or data modelling for graph databases like Neo4J, Neptune, etc.
- API experience using FastAPI, Flask, Spring Boot or equivalent.
- Interests or experience in Geopolitics, Sanction Compliance, or Financial Risk.

About Kharon:
Operating at the nexus of global security, Kharon is on a mission to revolutionize the current landscape. We take really complex data as it relates to global security and empower our clients to not only understand the risk associated with their potential business relationships but to operationalize that data so that they can make the best and most informed decisions possible.

Reporting to the Associate Director of Engineering, this role is critical to driving the evolution of the data infrastructure that underpins our intelligence platform. In this senior technical role, you will lead the design and implementation of scalable systems and resilient ETL pipelines that support a growing suite of analytic products.

Benefits:
- Fully sponsored medical, dental, and vision
- FSA program for both medical and dependent care
- 401k + Roth with matching and immediate vesting
- Paid time off + 11 paid holidays

The base salary range at Kharon is set between $230,000 - $280,000.
        """,
        "expected": {
            "job_family": "data",
            "job_subfamily": "data_engineer",
            "seniority": "staff_principal",
            "city_code": "den",
            "working_arrangement": "hybrid"
        }
    },
    {
        "source": "manual",
        "url": "https://www.linkedin.com/jobs/view/director-product-ai-data-brij-nyc",
        "posted_date": date(2025, 10, 11),
        "last_seen_date": date(2025, 11, 11),
        "raw_text": """
Director of Product – AI & Data Applications
Brij · New York, NY · 1 month ago
$160,000 - $210,000 + equity + benefits · Full-time
Location: Remote or Hybrid (NYC or Austin Preferred)

About Us:
Brij is a venture-backed, high-growth software startup based in NYC. Our AI-powered platform helps omnichannel consumer brands gain valuable data to "bridge" online and offline audiences to drive revenue across channels. We empower brands like Heineken, Feastables, Momofuku, Health-Ade, Skullcandy, and Gozney with tools that supercharge engagement through warranty registration, sweepstakes, rebates, and more.

The Role:
We're seeking a Director of Product – AI & Data Applications to own Brij's product strategy and execution, with a particular focus on building AI-and data-powered experiences across our platform.

This highly technical and strategic role is perfect for someone who has taken products from 0 → 1 and scaled them from 1 → 100, and who thrives at the intersection of generative AI, data infrastructure, and product design.

You'll set the product vision and build AI-native features that turn customer and product data into differentiated experiences—driving everything from intelligent automation to next-generation consumer insights. You'll also act as the on-the-road product voice, bringing market feedback and customer stories back into strategy while working closely with engineering, design, marketing, and sales.

What You'll Do:

Vision & Roadmap:
- Define the product vision and a rolling 1-year roadmap focused on delivering AI- and data-driven applications that delight customers and create competitive advantage
- Lead quarterly planning and ensure long-term strategy is aligned with execution
- Build transparent communication flows across engineering, go-to-market, and customer-facing teams
- Foster a strong product culture that is user-centric, data-informed, and AI-forward

Customer & Market Insights:
- Lead qualitative interviews and quantitative research to uncover customer pain points
- Turn customer and product data into marketing stories, best-practice guides, and insights for AI-powered features
- Conduct competitive analysis to identify opportunities for differentiation in AI and data capabilities

Go-to-Market & Sales Enablement:
- Serve as the on-the-road product voice in sales calls, customer meetings, and industry events
- Partner with marketing to refine positioning and messaging
- Create sales enablement content, training, case studies, and testimonials
- Build and nurture a customer community around Brij's AI and data innovations

Product Delivery & Scaling:
- Work closely with engineering and design to deliver impactful AI- and data-centric features from concept to launch
- Write clear product requirements and technical specs, ensuring speed, quality, and scalability
- Drive post-launch scaling and optimization
- Define and track KPIs that align product outcomes with business goals

Thought Leadership & Technical Direction:
- Build in public by posting on LinkedIn and other channels, sharing product updates and AI/data breakthroughs
- Act as the technical voice on architecture, API strategy, machine learning opportunities, and infrastructure decisions

Who You Are:
- 10+ years of product management or product leadership in high-growth SaaS or B2B, ideally in retail or e-commerce tech
- Proven success taking products 0→1→100 and scaling product processes that drive impact
- Strong technical foundation (CS/engineering degree or equivalent experience) with fluency in APIs, scalability, and architecture
- Deep background in AI and/or data is a major plus—experience building AI-native products, leveraging machine learning, or turning large datasets into actionable insights
- Skilled communicator and storyteller who can bridge technical and commercial teams
- Customer-obsessed and highly analytical
- High EQ leader who thrives on ownership, action, and cross-functional collaboration

Why Join Brij:
- Impact: Lead product innovation in AI and data within a fast-growing category with top-tier customers
- Growth: Work directly with Brij's founders and leadership team
- Flexibility: Hybrid work model with NYC HQ access
- Compensation: Competitive salary, equity, and benefits
- Culture: High-ownership, low-ego, customer-obsessed team
        """,
        "expected": {
            "job_family": "product",
            "job_subfamily": "ai_ml_pm",
            "seniority": "director_plus",
            "city_code": "nyc",
            "working_arrangement": "flexible"
        }
    },
    {
        "source": "manual",
        "url": "https://www.linkedin.com/jobs/view/data-architect-ascendion-london",
        "posted_date": date(2025, 10, 14),
        "last_seen_date": date(2025, 11, 11),
        "raw_text": """
Data Architect
Ascendion · London Area, United Kingdom (Hybrid) · 4 weeks ago
Full-time · Hybrid

Job Title: Data Strategy Consultant / Data Architect
Location: London, UK (Hybrid)

About the Role:
We are seeking an experienced Data Strategy Consultant / Data Architect to lead and deliver data strategy initiatives focused on discovery, governance, and integration within complex Merger and Demerger (M&A) environments. The ideal candidate will combine strong technical expertise in data architecture with strategic consulting skills to design and implement data strategies that enable business continuity, compliance, and value realization during organizational transitions.

Key Responsibilities:
- Lead the data strategy and architecture workstream for merger/demerger projects, aligning data initiatives with overall business transformation goals
- Conduct data discovery and assessment activities to identify data sources, quality issues, dependencies, and integration needs
- Develop and implement data governance frameworks, ensuring compliance, consistency, and control across systems and entities
- Define target data architectures and transition roadmaps to support the separation or integration of systems
- Create and maintain data models, dictionaries, lineage documentation, and related artefacts
- Advise on data platform choices (on-premises or cloud) to optimize performance, scalability, and compliance

Key Skills & Experience:
- Proven experience (8+ years) as a Data Architect, Data Strategy Consultant, or similar role
- Strong understanding of data governance, data management, metadata management, and data quality principles
- Demonstrated experience delivering data strategies for M&A or corporate restructuring (merger/demerger) projects
- Expertise in data discovery, data lineage, and data mapping activities
- Familiarity with data frameworks and standards such as DAMA-DMBOK, DCAM, or EDM Council best practices
- Hands-on experience with data platforms (e.g., Azure, AWS, GCP), data cataloging tools (e.g., Collibra, Alation, Informatica), and ETL/Integration solutions
- Excellent stakeholder management and communication skills, with the ability to influence both business and technical teams
- Strong analytical, documentation, and presentation abilities
        """,
        "expected": {
            "job_family": "data",
            "job_subfamily": "data_architect",
            "seniority": "staff_principal",
            "city_code": "lon",
            "working_arrangement": "hybrid"
        }
    }
]


# ============================================
# Helper Functions
# ============================================

def validate_classification(actual: dict, expected: dict) -> bool:
    """Compare classification against expected values"""
    matches = True
    
    print("\n   Validation Results:")
    for key, expected_val in expected.items():
        # Navigate nested dict for actual value
        if key in ['job_family', 'job_subfamily', 'seniority', 'experience_range']:
            actual_val = actual['role'].get(key)
        elif key in ['city_code', 'working_arrangement']:
            actual_val = actual['location'].get(key)
        else:
            actual_val = actual.get(key)
        
        match = actual_val == expected_val
        matches = matches and match
        
        icon = "[OK]" if match else "[ERROR]"
        print(f"   {icon} {key}: expected={expected_val}, actual={actual_val}")
    
    return matches


# ============================================
# Main Test Function
# ============================================

def run_manual_test():
    """Run full pipeline test with ground truth jobs"""
    
    print("=" * 70)
    print("JOB CLASSIFICATION MANUAL TEST")
    print("=" * 70)
    
    # Test connection first
    print("\n[0/4] Testing database connection...")
    if not test_connection():
        print("[ERROR] Database connection failed. Check your .env file.")
        return
    
    results_summary = []
    
    for i, test_job in enumerate(TEST_JOBS, 1):
        print(f"\n{'='*70}")
        print(f"TEST JOB {i}/{len(TEST_JOBS)}")
        print(f"{'='*70}")
        
        # Extract title from raw_text (first non-empty line)
        title_line = [line.strip() for line in test_job['raw_text'].split('\n') if line.strip()][0]
        print(f"URL: {test_job['url']}")
        print(f"Title: {title_line}")
        
        try:
            # Step 1: Insert raw job
            print("\n[1/4] Inserting raw job...")
            raw_id = insert_raw_job(
                source=test_job['source'],
                posting_url=test_job['url'],
                raw_text=test_job['raw_text']
            )
            print(f"[OK] Raw job inserted: ID {raw_id}")
            
            # Step 2: Classify with Claude
            print("\n[2/4] Classifying with Claude 3.5 Haiku...")
            classification = classify_job_with_claude(test_job['raw_text'])
            
            print(f"[OK] Classification complete:")
            print(f"   Job Family: {classification['role']['job_family']}")
            print(f"   Subfamily: {classification['role'].get('job_subfamily')}")
            print(f"   Seniority: {classification['role'].get('seniority')}")
            print(f"   Track: {classification['role'].get('track')}")
            print(f"   City: {classification['location']['city_code']}")
            print(f"   Arrangement: {classification['location']['working_arrangement']}")
            print(f"   Skills: {len(classification.get('skills', []))} extracted")
            
            # Step 3: Insert enriched job
            print("\n[3/4] Inserting enriched job...")
            
            # Extract salary range if present
            salary_range = classification['compensation'].get('base_salary_range')
            salary_min = salary_range.get('min') if salary_range else None
            salary_max = salary_range.get('max') if salary_range else None
            
            enriched_id = insert_enriched_job(
                raw_job_id=raw_id,
                employer_name=classification['employer']['name'],
                title_display=classification['role']['title_display'],
                job_family=classification['role']['job_family'],
                job_subfamily=classification['role'].get('job_subfamily'),
                city_code=classification['location']['city_code'],
                working_arrangement=classification['location']['working_arrangement'],
                position_type=classification['role']['position_type'],
                posted_date=test_job['posted_date'],
                last_seen_date=test_job['last_seen_date'],
                # Optional fields
                seniority=classification['role'].get('seniority'),
                track=classification['role'].get('track'),
                experience_range=classification['role'].get('experience_range'),
                employer_department=classification['employer'].get('department'),
                employer_size=classification['employer'].get('company_size_estimate'),
                currency=classification['compensation'].get('currency'),
                salary_min=salary_min,
                salary_max=salary_max,
                equity_eligible=classification['compensation'].get('equity_eligible'),
                skills=classification.get('skills', [])
            )
            print(f"[OK] Enriched job inserted: ID {enriched_id}")
            
            # Step 4: Validate against expected
            print("\n[4/4] Validating classification...")
            matches = validate_classification(classification, test_job['expected'])
            
            results_summary.append({
                'job': i,
                'title': classification['role']['title_display'],
                'matches': matches
            })
            
            if matches:
                print("\n[OK] ALL CHECKS PASSED!")
            else:
                print("\n[WARNING] Some checks failed - review above")
                
        except Exception as e:
            print(f"\n[ERROR] Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results_summary.append({
                'job': i,
                'title': 'ERROR',
                'matches': False
            })
    
    # Final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    
    passed = sum(1 for r in results_summary if r['matches'])
    total = len(results_summary)
    
    print(f"\nResults: {passed}/{total} jobs classified correctly")
    print("\nDetails:")
    for result in results_summary:
        icon = "[OK]" if result['matches'] else "[ERROR]"
        print(f"  {icon} Job {result['job']}: {result['title']}")
    
    # Show database state
    print(f"\n{'='*70}")
    print("DATABASE STATE")
    print(f"{'='*70}")
    
    enriched_result = supabase.table("enriched_jobs").select("*").execute()
    print(f"\nTotal enriched jobs in database: {len(enriched_result.data)}")
    
    for job in enriched_result.data:
        print(f"\n  📋 {job['title_display']}")
        print(f"     Company: {job['employer_name']}")
        print(f"     Classification: {job['job_family']} → {job['job_subfamily']}")
        print(f"     Seniority: {job['seniority']} ({job['track']})")
        print(f"     Location: {job['city_code']} ({job['working_arrangement']})")
        if job['salary_min']:
            print(f"     Salary: {job['currency']} {job['salary_min']:,.0f} - {job['salary_max']:,.0f}")
        print(f"     Skills: {len(job['skills'])} extracted")
        if job['skills']:
            skill_names = [s['name'] for s in job['skills'][:5]]
            print(f"     Top skills: {', '.join(skill_names)}")


if __name__ == "__main__":
    run_manual_test()
