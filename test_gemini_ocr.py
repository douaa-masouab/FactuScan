import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
print(f"DEBUG: Using KEY: {GOOGLE_API_KEY[:4]}...")

def test_gemini_multimodal(filepath):
    if not GOOGLE_API_KEY:
        print("No GOOGLE_API_KEY found")
        return
    
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        with open(filepath, "rb") as f:
            file_data = f.read()
            
        prompt = """Act as a Moroccan accounting expert. Analyze the attached invoice image carefully.
        Extract: invoice_number, invoice_date, supplier, ice, ht_amount, vat_amount, total_amount."""
        
        content = [
            prompt,
            {
                "mime_type": "image/jpeg" if filepath.endswith(('.jpg', '.jpeg')) else "image/png",
                "data": file_data
            }
        ]
        
        response = model.generate_content(content)
        print("GEMINI RESPONSE:")
        print(response.text)
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    upload_dir = "uploads"
    files = [f for f in os.listdir(upload_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
    if files:
        test_gemini_multimodal(os.path.join(upload_dir, files[0]))
    else:
        print("No files found in uploads/")
