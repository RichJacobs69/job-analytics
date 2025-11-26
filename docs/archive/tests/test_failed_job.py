from classifier import classify_job_with_claude
import json

test_job = """
Location: London/Remote
Compensation: Equity-Only (Founding Team)
Type: Full-Time

Please note - We are not able to offer any form of visa or sponsorship

About Us
We’re an ambitious AI startup on a mission to reshape how people interact with technology. Our product sits at the intersection of artificial intelligence, human-centered design, and mobile-first experience. We're building something bold and impactful, and we’re looking for a technical partner to help bring this vision to life.

What We Offer
Founding team equity – An ownership stake in a high-growth startup.
Full technical ownership of a greenfield product.
A collaborative, product-driven team with deep vision and ambition.
Remote-first culture with flexibility, trust, and a focus on outcomes.
Flexible working - The ability to do this role part-time
What You Will Do
Build machine learning models for real-time processing and analysis of time-series data with high accuracy, low latency, and scalability.
Use knowledge of ML theory and practice to improve current state-of-the-art for models using time-series data.
Develop generalisable, cutting-edge unsupervised and supervised models
Apply critical thinking and first principles knowledge to develop optimisation algorithms.
Collaborate with data scientists, software engineers, and other internal stakeholders to align ML models, ensuring they meet performance and reliability requirements.
Deploy ML models to Edge compute devices and monitor performance using best practices for MLOps.
About You
Highly knowledgeable in ML theory, architectures, and design.
Knowledge of federated learning techniques.
Proficient in Python. Strong candidates may also be proficient in C++/Objective C.
Experience using multiple ML frameworks (such as PyTorch, TensorFlow, Scikit-Learn, JAX) and numerical libraries (such as NumPy and Pandas). Knowledge of edge-specific frameworks (i.e. TensorFlow Lite) is a plus.
Experience building ML models with time-series or sequential data (such as NLP), especially for long time sequences and real-time processing scenarios.
Familiarity with reinforcement learning (RL), computational graphs, and/or graph neural networks is a plus.
Knowledgeable in techniques to optimise ML models for inference in compute-limited scenarios (i.e. model distillation, pruning, dimensionality reduction, feature selection, parallelisation).
Familiar deploying models for fast, efficient inference on compute accelerators (TPUs or NPUs).Proficient in designing, implementing, and maintaining robust ML pipelines for end-to-end model lifecycle management. Experience benchmarking multiple models is a plus.
Proficient in Git or other version control systems.
Familiar with cloud platforms such as AWS, Azure, or Google Cloud.
Experience working with LLMs/RAG is a plus, especially in building a knowledgebase, chatbot, or for data analysis/summarisation. Familiarity with Agile methodologies and experience in collaborative, cross-functional teams.
Analytical thinker with the ability to solve complex problems efficiently.
"""

print("Testing classification...")
result = classify_job_with_claude(test_job)

print("\n" + "="*60)
print("CLASSIFICATION RESULT")
print("="*60)
print(json.dumps(result, indent=2))

# Check critical fields
print("\n" + "="*60)
print("VALIDATION CHECK")
print("="*60)
print(f"city_code: {result['location'].get('city_code')}")
print(f"employer_name: {result['employer'].get('name')}")
print(f"title_display: {result['role'].get('title_display')}")