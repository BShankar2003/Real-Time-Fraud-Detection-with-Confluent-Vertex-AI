import vertexai
from vertexai.generative_models import GenerativeModel

PROJECT_ID = "project-53a73f94-a208-4988-908"  # ✅ CORRECT PROJECT ID
LOCATION = "us-central1"

print("🔍 Testing Gemini API Connection...")
print(f"Project: {PROJECT_ID}")
print(f"Using: Application Default Credentials (gcloud)")
print("=" * 50)

try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    model = GenerativeModel("gemini-2.0-flash-exp")
    
    test_prompt = """Classify this transaction as FRAUD or LEGITIMATE:
    
    Amount: ₹75,000
    User: USER123
    Transactions in last minute: 15
    
    Respond with ONE WORD: FRAUD or LEGITIMATE"""
    
    print("📤 Sending test prompt to Gemini...")
    response = model.generate_content(test_prompt)
    
    print("✅ SUCCESS! Gemini API is working!")
    print(f"📥 Response: {response.text}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")