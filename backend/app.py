import os
import uuid
import json
import io
import base64
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
from PIL import Image
import pdf2image
import cv2
import numpy as np
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import easyocr
import re
import magic
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai

# Load configuration
load_dotenv()

# FINAL-ULTRA-MEGA-ROBUST API KEY DETECTION
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
OCR_SPACE_API_KEY = os.environ.get('OCR_SPACE_API_KEY')

# Scan all environment variables if not found
if not GOOGLE_API_KEY or not OCR_SPACE_API_KEY:
    for k, v in os.environ.items():
        if not v or not isinstance(v, str): continue
        k_upper = k.replace(' ', '_').upper()
        v_clean = v.strip().strip('"').strip("'")
        
        if not GOOGLE_API_KEY:
            if ("GOOGLE" in k_upper and "API" in k_upper) or "AIza" in v_clean:
                GOOGLE_API_KEY = v_clean
        
        if not OCR_SPACE_API_KEY:
            if "OCR_SPACE" in k_upper or (len(v_clean) == 15 and v_clean.isalnum() and v_clean.startswith('K')):
                OCR_SPACE_API_KEY = v_clean

if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        print(f"[SYSTEM] Gemini IA activée.")
    except Exception as e:
        print(f"[ERROR] failed to configure Gemini: {e}")

if OCR_SPACE_API_KEY:
    print(f"[SYSTEM] OCR.Space activé.")

# Initialize Flask app
# Tell Flask where templates and static files live (frontend/ folder)
app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static')
)
CORS(app)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['SECRET_KEY'] = os.urandom(24)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database configuration and connection
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '3306')
DB_USER = os.environ.get('DB_USER', 'factuscan_user')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'secure_password')
DB_NAME = os.environ.get('DB_NAME', 'factuscan')

# Attempt connection with real test
DB_AVAILABLE = False
engine = None
Session = None
Base = declarative_base()

def init_db():
    global DB_AVAILABLE, engine, Session
    # 1. Try MySQL (if not on a localhost default that likely fails)
    if DB_HOST != 'localhost' or os.environ.get('MYSQL_URL'):
        try:
            db_uri = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            temp_engine = create_engine(db_uri, pool_pre_ping=True, connect_args={'connect_timeout': 3})
            with temp_engine.connect() as conn:
                pass
            engine = temp_engine
            Session = sessionmaker(bind=engine)
            DB_AVAILABLE = True
            print("[SUCCESS] MySQL Database connected.")
            return
        except Exception as e:
            print(f"[WARNING] MySQL connection failed ({e}).")

    # 2. Fallback to SQLite
    try:
        db_uri = "sqlite:///factuscan.db"
        engine = create_engine(db_uri, connect_args={'check_same_thread': False})
        Session = sessionmaker(bind=engine)
        with engine.connect() as conn:
            pass
        DB_AVAILABLE = True
        print("[INFO] Using SQLite local database.")
    except Exception as e:
        print(f"[ERROR] All fallbacks failed: {e}")
        DB_AVAILABLE = False

init_db()
# Create a global session for simple context
session = Session() if Session else None

# Database Models
class Invoice(Base):
    __tablename__ = 'invoices'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255))
    invoice_number = Column(String(100))
    invoice_date = Column(String(50))
    supplier = Column(String(255))
    ice = Column(String(50))
    ht_amount = Column(Float)
    vat_amount = Column(Float)
    total_amount = Column(Float)
    extracted_text = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

# Create tables (only if DB is available)
if DB_AVAILABLE:
    try:
        Base.metadata.create_all(engine)
        # Manual migration for existing databases: add ht_amount if missing
        with engine.connect() as conn:
            from sqlalchemy import inspect, text
            inspector = inspect(engine)
            columns = [c['name'] for c in inspector.get_columns('invoices')]
            if 'ht_amount' not in columns:
                print("[INFO] Adding missing column 'ht_amount' to invoices table...")
                conn.execute(text("ALTER TABLE invoices ADD COLUMN ht_amount FLOAT"))
                conn.commit()
    except Exception as e:
        print(f"[WARNING] Database initialization/migration error: {e}")

# Initialize OCR reader
reader = easyocr.Reader(['fr'], gpu=False)

# Helper functions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'jfif', 'jpe'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_with_gemini_multimodal(filepath, mime_type):
    """Send image/PDF directly to Gemini to extract data using vision-language capabilities"""
    if not GOOGLE_API_KEY:
        return None, None
    
    try:
        # Open file as binary
        with open(filepath, "rb") as f:
            file_data = f.read()
            
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Prepare content parts
        prompt = """Act as a Moroccan accounting expert. Analyze the attached invoice image carefully.
        Extract the following fields and return ONLY a valid JSON object:
        {
          "invoice_number": "number or dash if missing",
          "invoice_date": "DD/MM/YYYY",
          "supplier": "Company Name",
          "ice": "15-digit number",
          "ht_amount": float,
          "vat_amount": float,
          "total_amount": float,
          "raw_text": "A full precise transcription of all visible text"
        }
        Be accurate with amounts. If a number has a comma, use a dot. Return null for fields you cannot find with high confidence."""
        
        content = [
            prompt,
            {
                "mime_type": mime_type,
                "data": file_data
            }
        ]
        
        response = model.generate_content(content)
        
        # Robust response checking
        if not response or not response.candidates:
             print("[GEMINI ERROR] No candidates.")
             return None, None
             
        t = response.text.strip()
        print(f"[GEMINI RAW] {t[:100]}...") # Log start of response
        
        # Improved JSON Extraction from likely markdown blocks
        clean_json = t.replace('```json', '').replace('```', '').strip()
        if "{" in clean_json and "}" in clean_json:
            try:
                start = clean_json.find("{")
                end = clean_json.rfind("}") + 1
                data = json.loads(clean_json[start:end])
                
                # Format cleaning
                for field in ['ht_amount', 'vat_amount', 'total_amount']:
                    val = data.get(field)
                    if isinstance(val, str):
                        try:
                            data[field] = float(val.replace(' ', '').replace(',', '.'))
                        except:
                            data[field] = None
                
                return data, data.get('raw_text', "Données extraites par Gemini AI.")
            except Exception as e:
                print(f"[JSON ERROR] {e}")
                
        return None, None
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"[CRITICAL GEMINI ERROR]\n{error_msg}")
        return None, None

def extract_text_from_image(image_path):
    """Extract text from image using EasyOCR (fallback)"""
    try:
        # Compatibility fix for newer Pillow versions
        if not hasattr(Image, 'ANTIALIAS'):
            import PIL.Image
            if not hasattr(PIL.Image, 'ANTIALIAS'):
                setattr(PIL.Image, 'ANTIALIAS', getattr(PIL.Image, 'LANCZOS', getattr(PIL.Image, 'BICUBIC', 1)))
        
        result = reader.readtext(image_path)
        text = ' '.join([item[1] for item in result])
        return text
    except Exception as e:
        error_msg = str(e)
        print(f"Error extracting text: {error_msg}")
        return f"[ERROR: {error_msg}]"

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using pdf2image and EasyOCR (fallback)"""
    try:
        images = pdf2image.convert_from_path(pdf_path)
        all_text = ""
        for image in images:
            img_array = np.array(image)
            result = reader.readtext(img_array)
            text = ' '.join([item[1] for item in result])
            all_text += text + " "
        return all_text
    except Exception as e:
        error_msg = str(e)
        print(f"Error extracting text from PDF: {error_msg}")
        return f"[ERROR PDF: {error_msg}]"

import requests # Ajouté pour OCR.Space et Z.IA

def extract_with_zai(filepath):
    """Extraction avec Z.IA (BigModel GLM-OCR) - Très précis"""
    zai_key = os.environ.get('Z_AI_API_KEY')
    if not zai_key:
        return None
    
    try:
        print("[Z.IA] Tentative d'extraction...")
        headers = {"Authorization": f"Bearer {zai_key}"}
        
        # 1. Upload
        with open(filepath, "rb") as f:
            files = {'file': (os.path.basename(filepath), f, 'application/octet-stream')}
            r_up = requests.post("https://open.bigmodel.cn/api/paas/v4/files", 
                               headers=headers, files=files, data={'purpose': 'agent'}, timeout=30)
        
        if r_up.status_code != 200: return None
        file_id = r_up.json().get("id")
        
        # 2. Parse
        payload = {"model": "glm-ocr", "file": file_id}
        response = requests.post("https://open.bigmodel.cn/api/paas/v4/layout_parsing", 
                               headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            return response.json().get("content", "")
    except Exception as e:
        print(f"[Z.IA ERROR] {e}")
    return None

def extract_text_with_ocr_space(filepath):
    """Extract text using OCR.Space API (Powerful Free Cloud OCR)"""
    ocr_key = os.environ.get('OCR_SPACE_API_KEY')
    if not ocr_key:
        return None
    
    try:
        print(f"[OCR.SPACE] Traitement de {filepath}...")
        payload = {
            'apikey': ocr_key,
            'language': 'fre',
            'isOverlayRequired': False,
            'FileType': 'Auto',
            'isTable': True,
            'OCREngine': '2',
        }
        
        with open(filepath, 'rb') as f:
            r = requests.post('https://api.ocr.space/parse/image',
                            files={'filename': f},
                            data=payload,
                            timeout=60)
            
        result = r.json()
        if result.get('OCRExitCode') == 1:
            parsed_results = result.get('ParsedResults', [])
            if parsed_results:
                return parsed_results[0].get('ParsedText', '')
        
        return None
    except Exception as e:
        print(f"[OCR.SPACE ERROR] {e}")
        return None

def extract_invoice_data(text):
    """Extract invoice data from OCR text using regex patterns (Robust Moroccan Mode)"""
    data = {
        'invoice_number': None,
        'invoice_date': None,
        'supplier': None,
        'ice': None,
        'ht_amount': None,
        'vat_amount': None,
        'total_amount': None
    }
    
    # 1. ICE Detection (MUST BE 15 digits)
    ice_match = re.search(r'ICE\s*[:#]?\s*([0-9]{15})', text, re.IGNORECASE)
    if not ice_match:
        # Fallback: find any 15-digit number that isn't already assigned
        ice_match = re.search(r'([0-9]{15})', text)
        
    if ice_match:
        data['ice'] = ice_match.group(1)

    # 2. Invoice number patterns (Restricted to digits and dashes)
    invoice_num_patterns = [
        r'N[o.]\s*[:]?\s*([0-9-]+)',
        r'facture\s*[:#-]?\s*([0-9-]{4,})',
        r'invoice\s*[:#-]?\s*([0-9-]{4,})',
        r'N[°°]\s*facture\s*[:#]?\s*([0-9-]+)'
    ]
    
    for pattern in invoice_num_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            # If length is reasonable for a number
            if 3 < len(val) < 20:
                data['invoice_number'] = val
                break
            
    if not data['invoice_number']:
        data['invoice_number'] = '_'
    
    # 3. Date patterns (plus robustes)
    date_patterns = [
        r'date\s*[:#]?\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
        r'date\s*[:#]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'Le\s*(\d{1,2}\s*[a-zéA-Z]+\s*\d{2,4})', 
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            found_date = match.group(1).strip()
            # On vérifie que ce n'est pas juste l'année (4 chiffres seuls)
            if len(found_date) >= 8:
                data['invoice_date'] = found_date
                break
    
    # 4. Supplier patterns
    if "REDAL" in text.upper(): data['supplier'] = "REDAL"
    elif "LYDEC" in text.upper(): data['supplier'] = "LYDEC"
    elif "IAM" in text.upper() or "TELECOM" in text.upper(): data['supplier'] = "MAROC TELECOM"
    elif "MAROC" in text.upper() and "TELECOM" in text.upper(): data['supplier'] = "MAROC TELECOM"
    else:
        supplier_patterns = [
            r'fournisseur\s*[:#]?\s*([A-Za-z.\s]{3,})',
            r'soci[ée]t[ée]\s*([A-Za-z.\s]{3,})'
        ]
        for pattern in supplier_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 3:
                    data['supplier'] = name
                    break
    
    # 5. Amount/Total patterns (Flexible numbers)
    def clean_amount(s):
        if not s: return None
        # Remove everything except numbers, dot and comma
        val = re.sub(r'[^0-9.,]', '', s).replace(',', '.')
        # Handle cases with multiple dots (e.g. 1.000.00)
        if val.count('.') > 1:
            parts = val.split('.')
            val = "".join(parts[:-1]) + "." + parts[-1]
        try:
            return float(val)
        except:
            return None

    # Search for TTC Total
    total_patterns = [
        r'TOTAL\s+A\s+PAYER\s*[:#]?\s*([0-9.,\s]{1,15})',
        r'SOMME\s+A\s+PAYER\s*[:#]?\s*([0-9.,\s]{1,15})',
        r'total\s*ttc\s*[:#]?\s*([0-9.,\s]{1,15})',
        r'ttc\s*[:#]?\s*([0-9.,\s]{1,15})',
        r'net\s*a\s*payer\s*[:#]?\s*([0-9.,\s]{1,15})',
        r'total\s*[:#]?\s*([0-9.,\s]{4,15})' 
    ]
    # On cherche les patterns, mais on valide que ce ne sont pas des IDs (trop longs)
    for p in total_patterns:
        matches = re.finditer(p, text, re.IGNORECASE)
        # On prend le DERNIER match trouvé (le total est en bas)
        results = list(matches)
        if results:
            match = results[-1] # Le plus en bas possible
            val_str = match.group(1).strip()
            num_match = re.search(r'^([0-9\s.,]+)', val_str)
            if num_match:
                val = clean_amount(num_match.group(1))
                # SANITY CHECK: Un total de facture ne devrait pas dépasser 100 000 DH pour ce cas d'usage
                # Et ne doit pas ressembler à un matricule (pas plus de 7-8 chiffres significatifs)
                if val and 1 < val < 100000: 
                    data['total_amount'] = val
                    break

    # Search for HT Subtotal
    ht_patterns = [
        r'SOMME\s+HORS\s+TAXES\s*[:#]?\s*([0-9.,\s]+)',
        r'total\s*ht\s*[:#]?\s*([0-9.,\s]+)',
        r'ht\s*[:#]?\s*([0-9.,\s]+)',
        r'sous-total\s*[:#]?\s*([0-9.,\s]+)',
        r'montant\s*ht\s*[:#]?\s*([0-9.,\s]+)',
        r'MNT\s*HT\s*[:#]?\s*([0-9.,\s]+)'
    ]
    for p in ht_patterns:
        matches = list(re.finditer(p, text, re.IGNORECASE))
        if matches:
            match = matches[-1] # Toujours le plus en bas
            val = clean_amount(match.group(1))
            if val and val < 100000:
                data['ht_amount'] = val
                break
    
    # LAST RESORT: Find the largest number in the text
    if not data.get('total_amount'):
        # Look for patterns like "1 200,00" or "1200.00" followed by DH/MAD or at end of strings
        all_numbers = re.findall(r'([0-9]{1,3}(?:\s?[0-9]{3})*[.,]\s?[0-9]{2})\s*(?:DH|MAD|&|€|\b|$)', text)
        if all_numbers:
            amounts = [clean_amount(n) for n in all_numbers]
            valid_amounts = [a for a in amounts if a and a > 10]
            if valid_amounts:
                data['total_amount'] = max(valid_amounts)

    # VAT (Try to catch amount, not rate)
    # If 20% is found, keep it as rate, but we need amount
    vat_patterns = [
        r'montant\s*tva\s*[:#]?\s*([0-9.,\s]+)',
        r'tva\s*[:#]?\s*([0-9.,\s]{2,})\s*(?!%)' # Match digits NOT followed by %
    ]
    for p in vat_patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            # Check if it's followed by % in the nearby text
            if '%' not in text[match.end():match.end()+5]:
                val = clean_amount(match.group(1))
                # SANITY CHECK: VAT cannot be larger than the total or the HT
                if val and (not data.get('total_amount') or val < data['total_amount']):
                    data['vat_amount'] = val
                    break

    # SMART RECOVERY/CALCULATION
    # If we have Total and TVA rate is found elsewhere
    if data.get('total_amount') and not data.get('vat_amount'):
        match_rate = re.search(r'(\d{1,2})\s*%', text)
        if match_rate:
            rate = float(match_rate.group(1))
            data['vat_rate'] = rate # Store rate for UI
            # Calculate HT and TVA: TTC = HT * (1 + rate/100)
            data['ht_amount'] = round(data['total_amount'] / (1 + rate/100), 2)
            data['vat_amount'] = round(data['total_amount'] - data['ht_amount'], 2)
    
    # If we have HT and rate but no TTC
    elif data.get('ht_amount') and not data.get('total_amount'):
        match_rate = re.search(r'(\d{1,2})\s*%', text)
        if match_rate:
            rate = float(match_rate.group(1))
            data['vat_rate'] = rate
            data['vat_amount'] = round(data['ht_amount'] * (rate/100), 2)
            data['total_amount'] = round(data['ht_amount'] + data['vat_amount'], 2)
    
    # Simple subtraction if possible
    if data.get('total_amount') and data.get('ht_amount') and not data.get('vat_amount'):
        data['vat_amount'] = round(data['total_amount'] - data['ht_amount'], 2)
    elif data.get('total_amount') and data.get('vat_amount') and not data.get('ht_amount'):
        data['ht_amount'] = round(data['total_amount'] - data['vat_amount'], 2)
    
    return data

from dotenv import dotenv_values # Addition for dynamic key loading

def extract_with_gemini(text):
    """Refine extraction with Gemini LLM for better precision (Safe mode)"""
    try:
        from dotenv import dotenv_values
        env = dotenv_values()
        current_key = env.get('GOOGLE_API_KEY')
        if not current_key or "AIza" not in current_key:
            print("[GEMINI] Skipped: Invalid or missing API KEY in .env")
            return None
            
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Act as an expert Moroccan accountant. Extract data from this invoice text:
        {text}
        
        Return ONLY valid JSON:
        {{
            "invoice_number": "number",
            "invoice_date": "DD/MM/YYYY",
            "supplier": "Company Name (REDAL, LYDEC, etc.)",
            "ice": "15 digits",
            "ht_amount": float,
            "vat_amount": float,
            "total_amount": float
        }}
        """
        response = model.generate_content(prompt)
        text_resp = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text_resp[text_resp.find('{'):text_resp.rfind('}')+1])
        print(f"[GEMINI] Success for supplier: {data.get('supplier')}")
        return data
    except Exception as e:
        print(f"[GEMINI ERROR] {str(e)}")
        return None

def validate_data(data):
    """Validate ICE and check the sum: HT + TVA = Total"""
    validations = {
        'ice_valid': True,
        'math_valid': True,
        'errors': []
    }
    
    # 1. Check ICE (15 digits)
    if data.get('ice'):
        # Remove spaces/dots
        ice_clean = re.sub(r'[\s\.]', '', str(data['ice']))
        if not re.match(r'^\d{15}$', ice_clean):
            validations['ice_valid'] = False
            validations['errors'].append("L'ICE doit comporter exactement 15 chiffres.")
    else:
        validations['ice_valid'] = False
        validations['errors'].append("ICE introuvable ou illisible.")
    
    # 2. Check math: HT + VAT ~= Total (with a small margin for rounding)
    ht = data.get('ht_amount') or 0
    vat = data.get('vat_amount') or 0
    total = data.get('total_amount') or 0
    
    if total > 0:
        calculated_total = ht + vat
        if abs(calculated_total - total) > 0.05: # Allow 0.05 MAD margin
            validations['math_valid'] = False
            validations['errors'].append(f"Erreur de calcul: HT ({ht}) + TVA ({vat}) = {calculated_total:.2f} (diffère de {total:.2f})")
    else:
        validations['math_valid'] = False
        validations['errors'].append("Montants (HT/TVA/TTC) introuvables ou illisibles.")
            
    return validations

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/scanner')
def scanner():
    return render_template('scanner.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/docs')
def docs():
    return render_template('docs.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        # Debug logging
        print(f"[UPLOAD] Request files: {request.files}")
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        if file and allowed_file(file.filename):
            # Generate unique filename
            filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Detect file type and normalize
            try:
                file_type = magic.from_file(filepath, mime=True)
                # Map variations to standard types for Gemini
                if 'jfif' in file_type or 'jpe' in file_type:
                    file_type = "image/jpeg"
            except:
                file_type = "image/jpeg"
                
            # Try Gemini Multimodal First (Best & Lightest)
            gemini_data, gemini_text = extract_with_gemini_multimodal(filepath, file_type)
            
            invoice_data = None
            extracted_text = gemini_text if gemini_text else "[Données extraites directement par Gemini AI]"
            
            if gemini_data:
                # Success with Gemini Multimodal
                invoice_data = gemini_data
                # Ensure HT estimation if possible
                if invoice_data.get('total_amount') and invoice_data.get('vat_amount') and not invoice_data.get('ht_amount'):
                    invoice_data['ht_amount'] = invoice_data['total_amount'] - invoice_data['vat_amount']
            else:
                # Final attempt to find the key at runtime (Hugging Face specific fix)
                found_key = None
                if not GOOGLE_API_KEY:
                    print(f"[DEBUG] Re-scanning env at upload time. Available vars: {list(os.environ.keys())}")
                    for k, v in os.environ.items():
                        # Normalization to find any variation of Google API Key
                        normalized_k = k.replace(' ', '_').upper()
                        if (v and v.strip().startswith("AIza")) or "GOOGLE" in normalized_k:
                            if v and v.strip().startswith("AIza"):
                                found_key = v.strip()
                                break
                    
                    if found_key:
                        globals()['GOOGLE_API_KEY'] = found_key
                        genai.configure(api_key=found_key)
                        print(f"[SUCCESS] FOUND KEY DYNAMICALLY: {found_key[:4]}...")
                        # RE-TRY MULTIMODAL immediately if we just found it!
                        gemini_data, gemini_text = extract_with_gemini_multimodal(filepath, file_type)
                        if gemini_data:
                            invoice_data = gemini_data
                            extracted_text = gemini_text or "[Extraction IA Directe]"
                            # In this case skip the OCR block below
                            # ... later
                
                # Alternative 0: Z.IA (Si configurer)
                if not invoice_data:
                    extracted_text = extract_with_zai(filepath)
                    if extracted_text:
                        print("[SUCCESS] Z.IA utilisé avec succès.")
                    else:
                        # Alternative 1: OCR.Space (Cloud Gratuit)
                        extracted_text = extract_text_with_ocr_space(filepath)
                    
                    # Alternative 2: Local OCR (EasyOCR) if OCR.Space failed or no key
                    if not extracted_text:
                        print("[FALLBACK] Utilisation de l'OCR local...")
                        if 'pdf' in file_type:
                            extracted_text = extract_text_from_pdf(filepath)
                        else:  # Image file
                            extracted_text = extract_text_from_image(filepath)
                
                if not extracted_text or extracted_text.startswith("[ERROR"):
                    return jsonify({"error": f"Échec de l'OCR local : {extracted_text or 'Mémoire insuffisante'}. Veuillez ajouter une clé GOOGLE_API_KEY pour utiliser l'IA."}), 422

                # Step 1: Basic Regex
                invoice_data = extract_invoice_data(extracted_text)
                
                # Step 2: Gemini Text Analysis (Refinement)
                refine_data = extract_with_gemini(extracted_text)
                if refine_data:
                    for key in invoice_data:
                        if refine_data.get(key) is not None:
                            invoice_data[key] = refine_data[key]

            # Validate the results
            validations = validate_data(invoice_data)
            
            # Save to database
            invoice_id = None
            if DB_AVAILABLE:
                try:
                    new_invoice = Invoice(
                        filename=filename,
                        invoice_number=invoice_data.get('invoice_number', '_'),
                        invoice_date=invoice_data.get('invoice_date'),
                        supplier=invoice_data.get('supplier'),
                        ice=invoice_data.get('ice'),
                        ht_amount=invoice_data.get('ht_amount'),
                        vat_amount=invoice_data.get('vat_amount'),
                        total_amount=invoice_data.get('total_amount'),
                        extracted_text=extracted_text
                    )
                    session.add(new_invoice)
                    session.commit()
                    invoice_id = new_invoice.id
                except Exception as db_e:
                    print(f"[DATABASE ERROR] {db_e}")
                    session.rollback()
            
            return jsonify({
                "id": invoice_id,
                "filename": filename,
                "extracted_data": invoice_data,
                "extracted_text": extracted_text,
                "validations": validations,
                "ai_active": GOOGLE_API_KEY is not None,
                "message": "Fichier traité avec succès"
            })
        
        return jsonify({"error": "Type de fichier non autorisé"}), 400
    except Exception as global_e:
        print(f"[GLOBAL UPLOAD ERROR] {global_e}")
        return jsonify({"error": f"Erreur interne: {str(global_e)}"}), 500

@app.route('/invoices', methods=['GET'])
def get_invoices():
    invoices = session.query(Invoice).all()
    result = []
    for invoice in invoices:
        result.append({
            "id": invoice.id,
            "filename": invoice.filename,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "supplier": invoice.supplier,
            "ice": invoice.ice,
            "vat_amount": invoice.vat_amount,
            "total_amount": invoice.total_amount,
            "created_at": invoice.created_at.isoformat()
        })
    return jsonify(result)

@app.route('/invoices/<int:invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    invoice = session.query(Invoice).filter_by(id=invoice_id).first()
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    
    return jsonify({
        "id": invoice.id,
        "filename": invoice.filename,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date,
        "supplier": invoice.supplier,
        "ice": invoice.ice,
        "vat_amount": invoice.vat_amount,
        "total_amount": invoice.total_amount,
        "extracted_text": invoice.extracted_text,
        "created_at": invoice.created_at.isoformat()
    })

@app.route('/invoices/<int:invoice_id>', methods=['PUT'])
def update_invoice(invoice_id):
    invoice = session.query(Invoice).filter_by(id=invoice_id).first()
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    
    data = request.json
    if 'invoice_number' in data:
        invoice.invoice_number = data['invoice_number']
    if 'invoice_date' in data:
        invoice.invoice_date = data['invoice_date']
    if 'supplier' in data:
        invoice.supplier = data['supplier']
    if 'ice' in data:
        invoice.ice = data['ice']
    if 'vat_amount' in data:
        invoice.vat_amount = float(data['vat_amount'])
    if 'total_amount' in data:
        invoice.total_amount = float(data['total_amount'])
    
    invoice.updated_at = datetime.now()
    session.commit()
    
    return jsonify({
        "message": "Invoice updated successfully",
        "invoice": {
            "id": invoice.id,
            "filename": invoice.filename,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "supplier": invoice.supplier,
            "ice": invoice.ice,
            "vat_amount": invoice.vat_amount,
            "total_amount": invoice.total_amount,
            "updated_at": invoice.updated_at.isoformat()
        }
    })

@app.route('/invoices/<int:invoice_id>', methods=['DELETE'])
def delete_invoice(invoice_id):
    invoice = session.query(Invoice).filter_by(id=invoice_id).first()
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    
    # Delete file from filesystem
    if invoice.filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], invoice.filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Error removing file {filepath}: {e}")
    
    # Delete from database
    session.delete(invoice)
    session.commit()
    
    return jsonify({"message": "Invoice deleted successfully"})

@app.route('/voice/command', methods=['POST'])
def voice_command():
    """Process voice command manually or with AI"""
    data = request.json
    command = data.get('command', '')
    
    if not command:
        return jsonify({"response": "Je n'ai pas entendu votre commande."})

    try:
        # Pre-process command
        cmd_lower = command.lower()
        
        # 1. Get current stats for context (always attempt)
        total_ttc = 0.0
        invoice_count = 0
        if DB_AVAILABLE:
            try:
                invoice_count = session.query(Invoice).count()
                total_ttc = float(session.query(Invoice).with_entities(func.coalesce(func.sum(Invoice.total_amount), 0.0)).scalar() or 0)
            except:
                pass

        # 2. KEYWORD FALLBACK (Works without AI)
        if "total" in cmd_lower or "combien" in cmd_lower or "montant" in cmd_lower:
            return jsonify({"response": f"D'après vos données, le montant total des factures est de {total_ttc:.2f} dirhams pour {invoice_count} factures."})
        
        if "résumé" in cmd_lower or "qu'est-ce que j'ai" in cmd_lower or "nombre" in cmd_lower:
            return jsonify({"response": f"Vous avez actuellement {invoice_count} factures enregistrées dans votre tableau de bord FactuScan."})

        if "aide" in cmd_lower or "comment" in cmd_lower or "peux-tu" in cmd_lower:
            return jsonify({"response": "Je peux vous donner le total de vos dépenses, le nombre de vos factures, ou lire à haute voix les résultats d'un scan. Dites 'total' ou 'résumé'."})

        # 3. SMART AI FALLBACK (If keywords don't match)
        if GOOGLE_API_KEY:
            try:
                context = f"Tu es l'assistant FactuScan. Tu aides avec les factures. Total: {total_ttc} DH. Invoices: {invoice_count}. Commande: {command}. Réponds court."
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(context)
                return jsonify({"response": response.text.strip()})
            except Exception as e:
                return jsonify({"response": f"Je comprends la commande '{command}', mais j'ai une erreur réseau. Le total est de {total_ttc} DH."})

        return jsonify({"response": f"Désolé, l'intelligence artificielle n'est pas configurée, mais je peux vous dire que vous avez {invoice_count} factures pour un total de {total_ttc:.2f} DH."})

    except Exception as e:
        return jsonify({"response": "Désolé, l'assistant est temporairement indisponible."})

@app.route('/voice/synthesize', methods=['POST'])
def synthesize_speech():
    """Convert text to speech"""
    data = request.json
    text = data.get('text', '')
    
    try:
        from gtts import gTTS
        import tempfile
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            tts = gTTS(text=text, lang='fr', slow=False)
            tts.save(tmp_file.name)
            
            # Read file and encode to base64
            with open(tmp_file.name, 'rb') as audio_file:
                audio_data = audio_file.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Clean up temp file
            os.unlink(tmp_file.name)
            
            return jsonify({
                "audio": audio_base64,
                "format": "mp3"
            })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/check_status', methods=['GET'])
def check_status():
    """Endpoint to check if the AI key and Database are correctly initialized"""
    return jsonify({
        "ai_active": GOOGLE_API_KEY is not None,
        "db_available": DB_AVAILABLE,
        "engine_type": "mysql" if "mysql" in str(engine) else "sqlite" if engine else "none",
        "key_preview": f"{GOOGLE_API_KEY[:4]}..." if GOOGLE_API_KEY else None
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
# Fin du fichier - Déploiement Forcé
