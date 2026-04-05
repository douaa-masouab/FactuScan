import os
import requests
import json
import base64
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

Z_AI_API_KEY = os.getenv("Z_AI_API_KEY")
# Configuration technique Z.IA (Essayer l'endpoint officiel si le premier est lent)
BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
# Autre option : "https://api.z.ai/api/paas/v4"

def test_zai_ocr(image_path):
    if not Z_AI_API_KEY:
        print("[ERREUR] Clé API Z_AI_API_KEY non trouvée dans le fichier .env")
        return

    print(f"--- Test de l'OCR Z.IA avec le fichier : {image_path} ---")
    
    headers = {
        "Authorization": f"Bearer {Z_AI_API_KEY}"
    }

    try:
        # Étape 1 : Uploader le fichier
        print("[1/2] Téléchargement du fichier vers Z.IA...")
        with open(image_path, "rb") as f:
            files = {
                'file': (os.path.basename(image_path), f, 'application/octet-stream')
            }
            data = {'purpose': 'agent'}
            upload_response = requests.post(f"{BASE_URL}/files", headers=headers, files=files, data=data, timeout=30)
        
        if upload_response.status_code != 200:
            print(f"[ERREUR UPLOAD] Status {upload_response.status_code}")
            print(upload_response.text)
            return

        file_id = upload_response.json().get("id")
        print(f"[SUCCÈS] Fichier uploadé, ID : {file_id}")

        # Étape 2 : Lancer le parsing OCR
        print("[2/2] Analyse OCR (GLM-OCR)...")
        payload = {
            "model": "glm-ocr",
            "file": file_id
        }
        
        # Le parsing peut être lent, on met un timeout plus élevé
        response = requests.post(f"{BASE_URL}/layout_parsing", headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print("[SUCCÈS] Analyse terminée.")
            # Afficher le contenu extrait
            content = result.get("content", "")
            if content:
                print("\n--- CONTENU EXTRAIT ---\n")
                print(content[:1000] + "..." if len(content) > 1000 else content)
            else:
                print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"[ERREUR ANALYSE] Status {response.status_code}")
            print(response.text)

    except requests.exceptions.Timeout:
        print("[ERREUR] Délai d'attente dépassé (Timeout). Le serveur est peut-être injoignable.")
    except Exception as e:
        print(f"[ERREUR CRITIQUE] {str(e)}")

    except Exception as e:
        print(f"[ERREUR CRITIQUE] {str(e)}")

if __name__ == "__main__":
    # Rechercher une image de test dans le dossier uploads s'il y en a une
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
    files = [f for f in os.listdir(upload_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
    
    if files:
        test_zai_ocr(os.path.join(upload_dir, files[0]))
    else:
        print("Veuillez placer une image de facture dans le dossier 'uploads' pour faire le test.")
