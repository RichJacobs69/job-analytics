"""
Analyze data jobs in Denver (den) from enriched_jobs table.

This script runs a comprehensive set of analytics queries on enriched_jobs
filtered by job_family='data' and city='den'.
"""

import sys
import os
from collections import Counter
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_connection import supabase


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80 + "\n")


def analyze_data_jobs_denver():
    """Run comprehensive analytics on data jobs in Denver"""
    
    print_section("DATA JOBS IN DENVER - COMPREHENSIVE ANALYSIS")
    
    # ============================================
    # 1. TOTAL COUNT
    # ============================================
    print_section("1. TOTAL COUNT OF DATA JOBS IN DENVER")
    
    try:
        result = supabase.table("enriched_jobs").select(
            "*", count="exact"
        ).eq("job_family", "data").eq("city_code", "den").execute()
        
        total_count = result.count
        print(f"Total data jobs in Denver: {total_count:,}")
        
        if total_count == 0:
            print("\n⚠️  No data jobs found for Denver. Exiting.")
            return
            
    except Exception as e:
        print(f"❌ Error getting total count: {e}")
        return
    
    # ============================================
    # 2. SKILLS ANALYSIS
    # ============================================
    print_section("2. MOST PROMINENT SKILLS")
    
    try:
        # Fetch all jobs with their skills
        result = supabase.table("enriched_jobs").select(
            "skills"
        ).eq("job_family", "data").eq("city_code", "den").execute()
        
        # Count all skills
        all_skills = []
        for job in result.data:
            if job.get("skills"):
                for skill in job["skills"]:
                    if isinstance(skill, dict) and "name" in skill:
                        all_skills.append(skill["name"])
                    elif isinstance(skill, str):
                        all_skills.append(skill)
        
        skill_counts = Counter(all_skills)
        top_skills = skill_counts.most_common(20)
        
        print(f"Total skills extracted: {len(all_skills):,}")
        print(f"Unique skills: {len(skill_counts):,}")
        print(f"\nTop 20 Skills:")
        print("-" * 60)
        for rank, (skill, count) in enumerate(top_skills, 1):
            percentage = (count / total_count) * 100
            print(f"{rank:2d}. {skill:30s} {count:5d} ({percentage:.1f}%)")
        
    except Exception as e:
        print(f"❌ Error analyzing skills: {e}")
    
    # ============================================
    # 3. SUB_FAMILY DISTRIBUTION (excluding null, min 10 records)
    # ============================================
    print_section("3. SUB_FAMILY DISTRIBUTION (excluding null, min 10 records)")
    
    try:
        result = supabase.table("enriched_jobs").select(
            "job_subfamily"
        ).eq("job_family", "data").eq("city_code", "den").not_.is_(
            "job_subfamily", "null"
        ).execute()
        
        subfamily_counts = Counter([job["job_subfamily"] for job in result.data])
        
        # Filter subfamilies with >= 10 records
        filtered_subfamilies = [(sf, count) for sf, count in subfamily_counts.items() if count >= 10]
        filtered_subfamilies.sort(key=lambda x: x[1], reverse=True)
        
        total_in_distribution = sum([count for _, count in filtered_subfamilies])
        
        print(f"Subfamilies with >= 10 records: {len(filtered_subfamilies)}")
        print(f"Total jobs in this distribution: {total_in_distribution:,}")
        print("-" * 70)
        for subfamily, count in filtered_subfamilies:
            percentage = (count / total_in_distribution) * 100
            print(f"{subfamily:40s} {count:5d} ({percentage:.1f}%)")
        
    except Exception as e:
        print(f"❌ Error analyzing subfamilies: {e}")
    
    # ============================================
    # 4. TOP 10 EMPLOYERS
    # ============================================
    print_section("4. TOP 10 EMPLOYERS")
    
    try:
        result = supabase.table("enriched_jobs").select(
            "employer_name"
        ).eq("job_family", "data").eq("city_code", "den").execute()
        
        employer_counts = Counter([job["employer_name"] for job in result.data if job.get("employer_name")])
        top_employers = employer_counts.most_common(10)
        
        print(f"Total unique employers: {len(employer_counts):,}")
        print(f"\nTop 10 Employers:")
        print("-" * 70)
        for rank, (employer, count) in enumerate(top_employers, 1):
            percentage = (count / total_count) * 100
            print(f"{rank:2d}. {employer:45s} {count:5d} ({percentage:.1f}%)")
        
    except Exception as e:
        print(f"❌ Error analyzing employers: {e}")
    
    # ============================================
    # 5. EMPLOYER SIZE DISTRIBUTION (excluding null)
    # ============================================
    print_section("5. EMPLOYER SIZE DISTRIBUTION (excluding null)")
    
    try:
        result = supabase.table("enriched_jobs").select(
            "employer_size"
        ).eq("job_family", "data").eq("city_code", "den").not_.is_(
            "employer_size", "null"
        ).execute()
        
        size_counts = Counter([job["employer_size"] for job in result.data])
        total_with_size = sum(size_counts.values())
        
        # Sort by logical size order if possible
        size_order = {
            "startup": 1,
            "small": 2,
            "medium": 3,
            "large": 4,
            "enterprise": 5
        }
        
        sorted_sizes = sorted(size_counts.items(), 
                            key=lambda x: size_order.get(x[0].lower() if x[0] else "", 999))
        
        print(f"Jobs with employer size data: {total_with_size:,} ({(total_with_size/total_count)*100:.1f}% of total)")
        print(f"Jobs without size data: {total_count - total_with_size:,}")
        print("\nDistribution:")
        print("-" * 70)
        for size, count in sorted_sizes:
            percentage = (count / total_with_size) * 100
            print(f"{size:20s} {count:5d} ({percentage:.1f}%)")
        
    except Exception as e:
        print(f"❌ Error analyzing employer size: {e}")
    
    # ============================================
    # 6. AVERAGE SALARY BY SUBFAMILY (excluding null)
    # ============================================
    print_section("6. AVERAGE SALARY BY SUBFAMILY (excluding null)")
    
    try:
        result = supabase.table("enriched_jobs").select(
            "job_subfamily, salary_min, salary_max"
        ).eq("job_family", "data").eq("city_code", "den").not_.is_(
            "job_subfamily", "null"
        ).not_.is_(
            "salary_min", "null"
        ).not_.is_(
            "salary_max", "null"
        ).execute()
        
        # Group by subfamily
        subfamily_salaries = {}
        for job in result.data:
            subfamily = job["job_subfamily"]
            salary_min = job["salary_min"]
            salary_max = job["salary_max"]
            
            if subfamily not in subfamily_salaries:
                subfamily_salaries[subfamily] = {
                    "min_values": [],
                    "max_values": [],
                    "count": 0
                }
            
            subfamily_salaries[subfamily]["min_values"].append(salary_min)
            subfamily_salaries[subfamily]["max_values"].append(salary_max)
            subfamily_salaries[subfamily]["count"] += 1
        
        # Calculate averages
        subfamily_avg = []
        for subfamily, data in subfamily_salaries.items():
            avg_min = sum(data["min_values"]) / len(data["min_values"])
            avg_max = sum(data["max_values"]) / len(data["max_values"])
            avg_midpoint = (avg_min + avg_max) / 2
            subfamily_avg.append({
                "subfamily": subfamily,
                "avg_min": avg_min,
                "avg_max": avg_max,
                "avg_midpoint": avg_midpoint,
                "count": data["count"]
            })
        
        # Sort by average midpoint
        subfamily_avg.sort(key=lambda x: x["avg_midpoint"], reverse=True)
        
        total_with_salary = sum([item["count"] for item in subfamily_avg])
        
        print(f"Jobs with salary data: {total_with_salary:,} ({(total_with_salary/total_count)*100:.1f}% of total)")
        print("\nAverage Salaries by Subfamily:")
        print("-" * 90)
        print(f"{'Subfamily':30s} {'Count':>6s} {'Avg Min':>12s} {'Avg Max':>12s} {'Midpoint':>12s}")
        print("-" * 90)
        
        for item in subfamily_avg:
            print(f"{item['subfamily']:30s} "
                  f"{item['count']:6d} "
                  f"${item['avg_min']:>11,.0f} "
                  f"${item['avg_max']:>11,.0f} "
                  f"${item['avg_midpoint']:>11,.0f}")
        
    except Exception as e:
        print(f"❌ Error analyzing salaries: {e}")
    
    # ============================================
    # SUMMARY STATISTICS
    # ============================================
    print_section("SUMMARY STATISTICS")
    
    try:
        # Get various metadata counts
        result = supabase.table("enriched_jobs").select(
            "employer_size, job_subfamily, salary_min, skills, working_arrangement, seniority"
        ).eq("job_family", "data").eq("city_code", "den").execute()
        
        jobs_with_size = sum(1 for job in result.data if job.get("employer_size"))
        jobs_with_subfamily = sum(1 for job in result.data if job.get("job_subfamily"))
        jobs_with_salary = sum(1 for job in result.data if job.get("salary_min"))
        jobs_with_skills = sum(1 for job in result.data if job.get("skills") and len(job["skills"]) > 0)
        jobs_with_arrangement = sum(1 for job in result.data if job.get("working_arrangement"))
        jobs_with_seniority = sum(1 for job in result.data if job.get("seniority"))
        
        print(f"Total Data Jobs in Denver: {total_count:,}")
        print(f"\nData Completeness:")
        print(f"  - Employer Size:        {jobs_with_size:5d} ({(jobs_with_size/total_count)*100:5.1f}%)")
        print(f"  - Job Subfamily:        {jobs_with_subfamily:5d} ({(jobs_with_subfamily/total_count)*100:5.1f}%)")
        print(f"  - Salary Data:          {jobs_with_salary:5d} ({(jobs_with_salary/total_count)*100:5.1f}%)")
        print(f"  - Skills Data:          {jobs_with_skills:5d} ({(jobs_with_skills/total_count)*100:5.1f}%)")
        print(f"  - Working Arrangement:  {jobs_with_arrangement:5d} ({(jobs_with_arrangement/total_count)*100:5.1f}%)")
        print(f"  - Seniority:            {jobs_with_seniority:5d} ({(jobs_with_seniority/total_count)*100:5.1f}%)")
        
    except Exception as e:
        print(f"❌ Error generating summary: {e}")
    
    print("\n" + "=" * 80)
    print(" ANALYSIS COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    analyze_data_jobs_denver()

