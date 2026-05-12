import os
from dotenv import load_dotenv
from groq import Groq
 
load_dotenv(dotenv_path=".env")
 
api_key = os.getenv("GROQ_API_KEY")
print("Loaded key:", api_key[:10] + "..." if api_key else "None")
 
if not api_key:
    raise ValueError("No Groq API key found. Check your .env file.")
 
client = Groq(api_key=api_key)
 
prompt = "Summarize this clinical note: Patient is a 45-year-old male presenting with a 3-day history of productive cough, low-grade fever (38.1°C), and fatigue."
 
response = client.chat.completions.create(
    model="llama3-8b-8192",
    messages=[
        {"role": "user", "content": prompt}
    ],
    max_tokens=512,
)
 
print(response.choices[0].message.content)