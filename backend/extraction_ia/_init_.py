import re
import json
from typing import Dict, Any, Optional

class InvoiceExtractor:
    def __init__(self):
        # Define regex patterns for invoice fields
        self.patterns = {
            'invoice_number': [
                r'facture\s*[:#]?\s*([A-Z0-9-/]+)',
                r'facture\s*n[°°]\s*([A-Z0-9-/]+)',
                r'فاتورة\s*[:#]?\s*([A-Z0-9-/]+)',
                r'N[°°]\s*facture\s*[:#]?\s*([A-Z0-9-/]+)'
            ],
            'invoice_date': [
                r'date\s*[:#]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'date\s*[:#]?\s*(\d{1,2}\s*\w+\s*\d{2,4})',
                r'تاريخ\s*[:#]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
            ],
            'supplier': [
                r'fournisseur\s*[:#]?\s*([A-Za-z0-9\s&\'-]+)',
                r'soci[ée]t[ée]\s*[:#]?\s*([A-Za-z0-9\s&\'-]+)',
                r'المورد\s*[:#]?\s*([A-Za-z0-9\s&\'-]+)'
            ],
            'ice': [
                r'ICE\s*[:#]?\s*([0-9]{15})',
                r'Identifiant\s*Commun\s*[:#]?\s*([0-9]{15})',
                r'رقم\s*الهوية\s*[:#]?\s*([0-9]{15})'
            ],
            'vat_amount': [
                r'TVA\s*[:#]?\s*([0-9.,]+\s*DH)',
                r'Taxe\s*sur\s*la\s*valeur\s*ajout[ée]e\s*[:#]?\s*([0-9.,]+\s*DH)',
                r'ضريبة\s*القيمة\s*المضافة\s*[:#]?\s*([0-9.,]+\s*DH)'
            ],
            'total_amount': [
                r'Total\s*[:#]?\s*([0-9.,]+\s*DH)',
                r'Montant\s*total\s*[:#]?\s*([0-9.,]+\s*DH)',
                r'المبلغ\s*الإجمالي\s*[:#]?\s*([0-9.,]+\s*DH)'
            ]
        }
    
    def extract(self, text: str) -> Dict[str, Any]:
        """Extract invoice data from OCR text"""
        result = {
            'invoice_number': None,
            'invoice_date': None,
            'supplier': None,
            'ice': None,
            'vat_amount': None,
            'total_amount': None
        }
        
        # Extract each field using its patterns
        for field, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    if field in ['vat_amount', 'total_amount']:
                        # Extract numeric value
                        value_match = re.search(r'([0-9.,]+)', match.group(1))
                        if value_match:
                            # Replace comma with dot for float conversion
                            result[field] = float(value_match.group(1).replace(',', '.'))
                    else:
                        result[field] = match.group(1).strip()
                    break
        
        return result
    
    def extract_with_confidence(self, text: str) -> Dict[str, Any]:
        """Extract invoice data with confidence scores"""
        result = {
            'invoice_number': {'value': None, 'confidence': 0.0},
            'invoice_date': {'value': None, 'confidence': 0.0},
            'supplier': {'value': None, 'confidence': 0.0},
            'ice': {'value': None, 'confidence': 0.0},
            'vat_amount': {'value': None, 'confidence': 0.0},
            'total_amount': {'value': None, 'confidence': 0.0}
        }
        
        # Extract each field using its patterns
        for field, patterns in self.patterns.items():
            best_match = None
            best_confidence = 0.0
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Simple confidence calculation based on pattern specificity
                    confidence = len(pattern) / 100  # Simple heuristic
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = match
            
            if best_match:
                if field in ['vat_amount', 'total_amount']:
                    # Extract numeric value
                    value_match = re.search(r'([0-9.,]+)', best_match.group(1))
                    if value_match:
                        # Replace comma with dot for float conversion
                        result[field]['value'] = float(value_match.group(1).replace(',', '.'))
                        result[field]['confidence'] = best_confidence
                else:
                    result[field]['value'] = best_match.group(1).strip()
                    result[field]['confidence'] = best_confidence
        
        return result