import os
import requests
import json
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")

def test_ocr_space(image_path):
    if not OCR_SPACE_API_KEY:
        print("[ERREUR] Clé API OCR_SPACE_API_KEY non trouvée dans le fichier .env")
        return

    print(f"--- Test de l'OCR Space avec le fichier : {image_path} ---")
    
    try:
        # Configuration des paramètres OCR.Space
        payload = {
            'apikey': OCR_SPACE_API_KEY,
            'language': 'fre',  # Français
            'isOverlayRequired': False,
            'FileType': 'Auto',
            'isTable': True,     # Meilleur pour les factures
            'OCREngine': '2',    # Utiliser le moteur 2 (plus rapide et souvent meilleur)
        }
        
        # Envoyer l'image
        with open(image_path, 'rb') as f:
            print("[INFO] Envoi en cours... (Délai d'attente augmenté à 60s)")
            r = requests.post('https://api.ocr.space/parse/image',
                            files={'filename': f},
                            data=payload,
                            timeout=60)
        
        result = r.json()
        
        if result.get('OCRExitCode') == 1:
            print("[SUCCÈS] Analyse terminée.")
            # Extraire le texte parsé
            parsed_results = result.get('ParsedResults', [])
            if parsed_results:
                text = parsed_results[0].get('ParsedText', '')
                print("\n--- TEXTE EXTRAIT ---\n")
                print(text)
            else:
                print("[ERREUR] Aucun texte n'a été extrait de l'image.")
        else:
            print(f"[ERREUR] Erreur de l'API OCR.Space :")
            print(json.dumps(result.get('ErrorMessage', 'Erreur inconnue'), indent=2))

    except requests.exceptions.Timeout:
        print("[ERREUR] Délai d'attente dépassé (Timeout). Le serveur est peut-être lent.")
    except Exception as e:
        print(f"[ERREUR CRITIQUE] {str(e)}")

if __name__ == "__main__":
    # Rechercher une image de test dans le dossier uploads
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
    files = [f for f in os.listdir(upload_dir) if f.endswith(('.jpg', '.png', '.jpeg', '.pdf'))]
    
    if files:
        # On prend la première image trouvée
        test_ocr_space(os.path.join(upload_dir, files[0]))
    else:
        print("Veuillez placer une image de facture dans le dossier 'uploads' pour faire le test.")
