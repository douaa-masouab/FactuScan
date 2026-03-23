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

# ULTRA-ROBUST API KEY DETECTION
GOOGLE_API_KEY = None
print("[DEBUG] Checking Environment Variables...")
for k, v in os.environ.items():
    # Look for anything that looks like a Google API Key
    clean_k = k.upper().strip()
    if clean_k in ['GOOGLE_API_KEY', 'CLÉ_API_GOOGLE', 'CLE_API_GOOGLE', 'GOOGLE_API_KEY_'] or 'CLÉ' in clean_k or 'GOOGLE_API' in clean_k:
        if v and v.strip().startswith("AIza"):
            GOOGLE_API_KEY = v.strip()
            print(f"[SUCCESS] Found API Key in variable: {k}")
            break

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("[WARNING] NO GOOGLE API KEY DETECTED! Ensure you have GOOGLE_API_KEY set in Railway.")

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
        return None
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Open file as binary
        with open(filepath, "rb") as f:
            file_data = f.read()
            
        content = [
            """Tu es un expert en comptabilité marocaine. 
            Analyse cette image de facture et extrais les données suivantes en JSON :
            - invoice_number: Numéro de facture
            - invoice_date: Date (format JJ/MM/AAAA)
            - supplier: Nom de l'entreprise/fournisseur
            - ice: Identifiant Commun de l'Entreprise (15 chiffres)
            - ht_amount: Montant Hors Taxe (nombre sans devise)
            - vat_amount: Montant de la TVA (nombre sans devise)
            - total_amount: Montant Total TTC (nombre sans devise)
            - raw_text: Le texte complet brut lisible sur la facture
            
            Réponds UNIQUEMENT avec le bloc JSON. Si une info est absente, mets null.""",
            {
                "mime_type": mime_type,
                "data": file_data
            }
        ]
        
        response = model.generate_content(content)
        t = response.text.strip()
        print(f"[GEMINI RAW RESP] {t}")  # Debug print
        
        # Find JSON block even if there is surrounding text
        if "{" in t and "}" in t:
            start = t.find("{")
            end = t.rfind("}") + 1
            json_text = t[start:end]
            data = json.loads(json_text)
            
            raw_text = data.get('raw_text', '')
            
            # Clean up amounts to be float
            for field in ['ht_amount', 'vat_amount', 'total_amount']:
                val = data.get(field)
                if val is not None:
                    try:
                        # Handle cases where model returns a string with comma or spaces
                        if isinstance(val, str):
                            val = val.replace(' ', '').replace(',', '.')
                        data[field] = float(val)
                    except ValueError:
                        data[field] = None
                        
            # Return both data and the full text explanation
            return data, raw_text
        return None, None
    except Exception as e:
        print(f"[Gemini Multimodal Error] {e}")
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

def extract_invoice_data(text):
    """Extract invoice data from OCR text using regex patterns"""
    data = {
        'invoice_number': None,
        'invoice_date': None,
        'supplier': None,
        'ice': None,
        'ht_amount': None,
        'vat_amount': None,
        'total_amount': None
    }
    
    # Invoice number patterns (French)
    # Use negative lookahead to avoid matching 'date', 'tva', 'total'
    invoice_num_patterns = [
        r'facture\s*[:#]?\s*(?!date|tva|total)([A-Z0-9-/]+)',
        r'facture\s*n[°°]\s*(?!date|tva|total)([A-Z0-9-/]+)',
        r'N[°°]\s*facture\s*[:#]?\s*(?!date|tva|total)([A-Z0-9-/]+)'
    ]
    
    for pattern in invoice_num_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['invoice_number'] = match.group(1).strip()
            break
            
    if not data['invoice_number']:
        data['invoice_number'] = '_'
    
    # Date patterns
    date_patterns = [
        r'date\s*[:#]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'date\s*[:#]?\s*(\d{1,2}\s*\w+\s*\d{2,4})'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['invoice_date'] = match.group(1)
            break
    
    # Supplier patterns
    supplier_patterns = [
        r'fournisseur\s*[:#]?\s*([A-Za-z0-9\s&\'-]+)',
        r'soci[ée]t[ée]\s*[:#]?\s*([A-Za-z0-9\s&\'-]+)'
    ]
    
    for pattern in supplier_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['supplier'] = match.group(1).strip()
            break
    
    # ICE (Moroccan tax ID) patterns
    ice_patterns = [
        r'ICE\s*[:#]?\s*([0-9]{15})',
        r'Identifiant\s*Commun\s*[:#]?\s*([0-9]{15})'
    ]
    
    for pattern in ice_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data['ice'] = match.group(1)
            break
    
    # VAT amount patterns
    vat_patterns = [
        r'TVA\s*[:#]?\s*([0-9.,]+\s*DH)',
        r'Taxe\s*sur\s*la\s*valeur\s*ajout[ée]e\s*[:#]?\s*([0-9.,]+\s*DH)'
    ]
    
    for pattern in vat_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Extract numeric value
            vat_value = re.search(r'([0-9.,]+)', match.group(1))
            if vat_value:
                # Replace comma with dot for float conversion
                data['vat_amount'] = float(vat_value.group(1).replace(',', '.'))
            break
    
    # Total amount patterns
    total_patterns = [
        r'Total\s*[:#]?\s*([0-9.,]+\s*DH)',
        r'Montant\s*total\s*[:#]?\s*([0-9.,]+\s*DH)'
    ]
    
    for pattern in total_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Extract numeric value
            total_value = re.search(r'([0-9.,]+)', match.group(1))
            if total_value:
                # Replace comma with dot for float conversion
                data['total_amount'] = float(total_value.group(1).replace(',', '.'))
            break
            
    # Estimate HT if missing but TVA and Total exist
    try:
        if data.get('total_amount') and data.get('vat_amount') and not data.get('ht_amount'):
            data['ht_amount'] = data['total_amount'] - data['vat_amount']
    except:
        pass
    
    return data

def extract_with_gemini(text):
    """Refine extraction with Gemini LLM for better precision"""
    if not GOOGLE_API_KEY:
        return None
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Extract invoice data from the following text in JSON format:
        Text: {text}
        
        Fields to extract:
        - invoice_number (string)
        - invoice_date (string)
        - supplier (string)
        - ice (string, 15 digits)
        - ht_amount (float)
        - vat_amount (float)
        - total_amount (float)
        
        Only return the JSON. If a value is missing, return null.
        """
        response = model.generate_content(prompt)
        # Handle cases where response might contain markdown code blocks
        json_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_text)
    except Exception as e:
        print(f"[Error] Gemini extraction failed: {e}")
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
            
            # Detect file type
            try:
                file_type = magic.from_file(filepath, mime=True)
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
                # Fallback to local OCR + Regex + Gemini Text analysis
                print("[INFO] Gemini Multimodal failed or key missing. Using local OCR fallback...")
                
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
# Fin du fichier - Déploiement Forcé
