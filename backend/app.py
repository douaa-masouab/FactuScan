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

# Load development configuration
load_dotenv()
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

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

# Database setup
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '3306')
DB_USER = os.environ.get('DB_USER', 'factuscan_user')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'secure_password')
DB_NAME = os.environ.get('DB_NAME', 'factuscan')

DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
Base = declarative_base()

try:
    engine = create_engine(DATABASE_URI, pool_pre_ping=True, connect_args={'connect_timeout': 5})
    Session = sessionmaker(bind=engine)
    session = Session()
    DB_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] MySQL unavailable ({e}). Falling back to SQLite...")
    try:
        # Fallback to local SQLite if MySQL fails
        DATABASE_URI = "sqlite:///factuscan.db"
        engine = create_engine(DATABASE_URI)
        Session = sessionmaker(bind=engine)
        session = Session()
        DB_AVAILABLE = True
    except Exception as e2:
        print(f"[ERROR] SQLite fallback failed: {e2}")
        engine = None
        session = None
        DB_AVAILABLE = False

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

def extract_text_from_image(image_path):
    """Extract text from image using EasyOCR"""
    try:
        result = reader.readtext(image_path)
        text = ' '.join([item[1] for item in result])
        return text
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ""

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using pdf2image and EasyOCR"""
    try:
        images = pdf2image.convert_from_path(pdf_path)
        all_text = ""
        for image in images:
            # Convert PIL image to numpy array
            img_array = np.array(image)
            # Extract text
            result = reader.readtext(img_array)
            text = ' '.join([item[1] for item in result])
            all_text += text + " "
        return all_text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""

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
    
    # 2. Check math: HT + VAT ~= Total (with a small margin for rounding)
    ht = data.get('ht_amount') or 0
    vat = data.get('vat_amount') or 0
    total = data.get('total_amount') or 0
    
    if total > 0:
        calculated_total = ht + vat
        if abs(calculated_total - total) > 0.05: # Allow 0.05 MAD margin
            validations['math_valid'] = False
            validations['errors'].append(f"Erreur de calcul: HT ({ht}) + TVA ({vat}) = {calculated_total:.2f} (différe de {total:.2f})")
            
    return validations

# Routes
@app.route('/')
def index():
    return render_template('index.html')

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
            
            # Extract text based on file type
            try:
                file_type = magic.from_file(filepath, mime=True)
            except:
                file_type = "image/jpeg"
                
            extracted_text = ""
            if 'pdf' in file_type:
                extracted_text = extract_text_from_pdf(filepath)
            else:  # Image file
                extracted_text = extract_text_from_image(filepath)
            
            if not extracted_text:
                return jsonify({"error": "Impossible d'extraire du texte de ce fichier."}), 422

            # Extract invoice data (Basic OCR/Regex)
            invoice_data = extract_invoice_data(extracted_text)
            
            # Refine with Gemini if possible
            try:
                gemini_data = extract_with_gemini(extracted_text)
                if gemini_data:
                    for key in invoice_data:
                        if gemini_data.get(key) is not None:
                            invoice_data[key] = gemini_data[key]
            except Exception as ge:
                print(f"[Gemini Error] {ge}")

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
                "validations": validations,
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
    """Process voice command and return response"""
    data = request.json
    command = data.get('command', '').lower()
    
    response = ""
    
    if 'résumé' in command or 'summary' in command:
        # Get recent invoices summary
        invoices = session.query(Invoice).order_by(Invoice.created_at.desc()).limit(5).all()
        total = sum(inv.total_amount or 0 for inv in invoices)
        count = len(invoices)
        
        response = f"Vous avez {count} factures récentes avec un total de {total:.2f} dirhams."
    
    elif 'total' in command:
        # Get total amount of all invoices
        total = session.query(Invoice).with_entities(func.coalesce(func.sum(Invoice.total_amount), 0)).scalar()
        
        response = f"Le montant total de toutes les factures est de {total:.2f} dirhams."
    
    elif 'aide' in command or 'help' in command:
        response = "Vous pouvez dire: résumé, total, ou réessayer l'OCR."
    
    else:
        response = "Désolé, je n'ai pas compris votre commande."
    
    return jsonify({"response": response})

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
