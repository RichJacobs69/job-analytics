"""
Test classifier on specific Adzuna job: Burberry Data Scientist
https://www.adzuna.co.uk/jobs/details/5518628087
"""

import sys
sys.path.insert(0, '.')
from pipeline.classifier import classify_job_with_claude
import json

# Job from Adzuna
title = 'Data Scientist'
company = 'Burberry'
category = 'IT Jobs'
location = 'London'
salary_min = 45000
salary_max = 50000

description = '''INTRODUCTION  
At Burberry, we believe creativity opens spaces. Our purpose is to unlock the power of imagination to push boundaries and open new possibilities for our people, our customers and our communities.

JOB PURPOSE  
We are now recruiting for a Data Scientist to join the Customer Data Science team. The Customer Data Science team uses advanced modelling techniques to uncover our customers behaviours, preferences and intent to purchase. We aim to deliver targeted and personalised experiences across all customer touchpoints in collaboration with business stakeholders.

As a Data Scientist, you will be accountable for building and deploying robust statistical and machine learning models, exploring a wide range of new data sources, and generating reliable and actionable insights and recommendations. You will work closely with other data scientists and engineers to develop innovative solutions to use cases across the business related to the Burberry customer. Some examples of current work include:

- Propensity modelling: developing models to understand how likely a client or prospect is to purchase
- Product recommendations & discovery algorithms: Serving customers with tailored product recommendations
- Client relationship intelligence: apply data-driven models and strategies

RESPONSIBILITIES  
- Generating robust advanced analytics and developing new cutting-edge machine learning models
- Optimising and evolving current models and analytics solutions in production
- Presenting analytics solutions, models and insights to business stakeholders
- Designing, evaluating and encouraging experimentation
- Working with latest data science & AI technologies

PERSONAL PROFILE  
- Advanced degree, MSc or PhD in a quantitative field (Data Science, Mathematics, Statistics, etc)
- Some experience as a Data Scientist in a commercial environment
- Solid foundation in programming and experienced in Python
- Experience in: time series, recommendation systems, deep learning or LLMs
- Strong problem-solving skills
- Good understanding of machine learning and deep learning techniques
'''

print('='*80)
print('TESTING CLASSIFIER ON BURBERRY DATA SCIENTIST JOB')
print('https://www.adzuna.co.uk/jobs/details/5518628087')
print('='*80)
print(f'Title: {title}')
print(f'Company: {company}')
print(f'Category: {category}')
print(f'Location: {location}')
print(f'Salary: {salary_min} - {salary_max} EUR')
print('='*80)

# Test with structured input
structured_input = {
    'title': title,
    'company': company,
    'description': description,
    'location': location,
    'category': category,
    'salary_min': salary_min,
    'salary_max': salary_max,
}

result = classify_job_with_claude(
    job_text=description,
    structured_input=structured_input,
    verbose=False
)

print('\nCLASSIFICATION RESULT:')
print('-'*40)
role = result.get('role', {})
print(f"job_family: {role.get('job_family')}")
print(f"job_subfamily: {role.get('job_subfamily')}")
print(f"seniority: {role.get('seniority')}")
print(f"title_display: {role.get('title_display')}")
print(f"track: {role.get('track')}")

location_result = result.get('location', {})
print(f"city_code: {location_result.get('city_code')}")
print(f"working_arrangement: {location_result.get('working_arrangement')}")

skills = result.get('skills', [])
skill_names = [s.get('name') for s in skills[:8]]
print(f"skills: {skill_names}")

comp = result.get('compensation', {})
salary_range = comp.get('base_salary_range', {})
print(f"salary: {salary_range.get('min')} - {salary_range.get('max')} {comp.get('currency')}")

print('\n' + '='*80)
print('EXPECTED vs ACTUAL')
print('='*80)
print(f"job_family: expected 'data' -> got '{role.get('job_family')}' {'✅' if role.get('job_family') == 'data' else '❌'}")
print(f"job_subfamily: expected 'data_scientist' -> got '{role.get('job_subfamily')}' {'✅' if role.get('job_subfamily') == 'data_scientist' else '❌'}")
print(f"city_code: expected 'lon' -> got '{location_result.get('city_code')}' {'✅' if location_result.get('city_code') == 'lon' else '❌'}")

