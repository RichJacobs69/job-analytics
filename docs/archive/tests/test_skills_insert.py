from db_connection import supabase

# Test inserting skills directly
test_skills = [
    {"name": "Python", "family_code": "programming"},
    {"name": "SQL", "family_code": "programming"}
]

result = supabase.table("enriched_jobs") \
    .update({"skills": test_skills}) \
    .eq("id", 5) \
    .execute()

print("Updated row:")
print(result.data)

# Verify it worked
verify = supabase.table("enriched_jobs") \
    .select("skills") \
    .eq("id", 5) \
    .execute()

print("\nSkills in database:")
print(verify.data[0]['skills'])