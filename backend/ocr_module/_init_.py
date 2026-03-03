import os
import cv2
import numpy as np
import easyocr
import pdf2image
from PIL import Image

class OCRProcessor:
    def __init__(self):
        self.reader = easyocr.Reader(['fr'], gpu=False)
    
    def process_image(self, image_path):
        """Process image file and extract text"""
        try:
            result = self.reader.readtext(image_path)
            text = ' '.join([item[1] for item in result])
            return text
        except Exception as e:
            print(f"Error extracting text from image: {e}")
            return ""
    
    def process_pdf(self, pdf_path):
        """Process PDF file and extract text"""
        try:
            images = pdf2image.convert_from_path(pdf_path)
            all_text = ""
            for image in images:
                # Convert PIL image to numpy array
                img_array = np.array(image)
                # Extract text
                result = self.reader.readtext(img_array)
                text = ' '.join([item[1] for item in result])
                all_text += text + " "
            return all_text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""
    
    def preprocess_image(self, image_path):
        """Preprocess image for better OCR results"""
        try:
            # Read image
            img = cv2.imread(image_path)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply threshold to get binary image
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(binary)
            
            # Save preprocessed image
            preprocessed_path = image_path.replace('.', '_preprocessed.')
            cv2.imwrite(preprocessed_path, denoised)
            
            return preprocessed_path
        except Exception as e:
            print(f"Error preprocessing image: {e}")
            return image_path