import os
import io
import base64
import json
from typing import Dict, Any, Optional
import speech_recognition as sr
from gtts import gTTS
import tempfile

class VoiceAssistant:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
    
    def recognize_speech(self, audio_data: bytes, language: str = 'fr-FR') -> Optional[str]:
        """Recognize speech from audio data"""
        try:
            # Create AudioFile object from audio data
            with tempfile.NamedTemporaryFile(suffix='.wav') as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
                
                # Use the audio file as the audio source
                with sr.AudioFile(temp_file_path) as source:
                    audio = self.recognizer.record(source)
                
                # Recognize speech using Google Speech Recognition
                try:
                    text = self.recognizer.recognize_google(audio, language=language)
                    return text
                except sr.UnknownValueError:
                    print("Google Speech Recognition could not understand audio")
                    return None
                except sr.RequestError as e:
                    print(f"Could not request results from Google Speech Recognition service; {e}")
                    return None
        except Exception as e:
            print(f"Error recognizing speech: {e}")
            return None
    
    def synthesize_speech(self, text: str) -> Optional[bytes]:
        """Synthesize speech from text"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                tts = gTTS(text=text, lang='fr', slow=False)
                tts.save(tmp_file.name)
                
                # Read file and return bytes
                with open(tmp_file.name, 'rb') as audio_file:
                    audio_data = audio_file.read()
                
                # Clean up temp file
                os.unlink(tmp_file.name)
                
                return audio_data
        except Exception as e:
            print(f"Error synthesizing speech: {e}")
            return None
    
    def process_command(self, command: str) -> Dict[str, Any]:
        """Process voice command and return response"""
        command = command.lower()
        response = ""
        action = None
        
        if 'résumé' in command or 'summary' in command:
            action = 'summary'
            response = "Voici un résumé de vos factures récentes."
        
        elif 'total' in command:
            action = 'total'
            response = "Le montant total de toutes vos factures est de 1,234.56 DH."
        
        elif 'aide' in command or 'help' in command:
            action = 'help'
            response = "Vous pouvez dire: résumé, total, ou réessayer l'OCR."
        
        elif 'réessayer' in command or 'retry' in command:
            action = 'retry'
            response = "Je vais réessayer l'OCR pour la dernière facture."
        
        else:
            response = "Désolé, je n'ai pas compris votre commande."
        
        return {
            'response': response,
            'action': action
        }
