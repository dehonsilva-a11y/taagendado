import os
import json
import base64
from datetime import timedelta
from flask import Flask
import firebase_admin
from firebase_admin import credentials, firestore
from whitenoise import WhiteNoise
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env automaticamente (se ele existir localmente)
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORIA_CACHE = {}

if not firebase_admin._apps:
    raw_creds = os.getenv("FIREBASE_CREDENTIALS", "").strip()
    
    if raw_creds:
        if not raw_creds.startswith('{'):
            raw_creds = base64.b64decode(raw_creds).decode('utf-8')
        cred_dict = json.loads(raw_creds)
        cred = credentials.Certificate(cred_dict)
    elif os.path.exists(os.path.join(BASE_DIR, "config", "firebase_key.json")):
        cred = credentials.Certificate(os.path.join(BASE_DIR, "config", "firebase_key.json"))
    elif os.path.exists(os.path.join(BASE_DIR, "firebase_key.json")):
        cred = credentials.Certificate(os.path.join(BASE_DIR, "firebase_key.json"))
    else:
        raise FileNotFoundError("Credenciais do Firebase não encontradas.")

    firebase_admin.initialize_app(cred)

db = firestore.client()

def create_app():
    app = Flask(__name__)
    app.wsgi_app = WhiteNoise(app.wsgi_app, root=os.path.join(BASE_DIR, 'app', 'static'), prefix='static/')
    
    # Puxa o SECRET_KEY limpo do ambiente. Se não achar, o sistema avisa na hora.
    app.secret_key = os.getenv('SECRET_KEY')
    if not app.secret_key:
        raise ValueError("ERRO FATAL: A variável SECRET_KEY não foi encontrada no ambiente ou .env!")
        
    app.permanent_session_lifetime = timedelta(minutes=15)

    from app.auth import auth_bp
    from app.routes import main_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app