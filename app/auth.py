import os
import time
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from firebase_admin import auth as firebase_auth
from app import db, MEMORIA_CACHE

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('main.home'))
        
    # Puxa as configurações do .env para mandar para o HTML
    firebase_config = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID")
    }
    
    return render_template('login.html', firebase_config=firebase_config)

# Rota renomeada para processar qualquer login do Firebase (Google, Apple, etc)
@auth_bp.route('/auth_token', methods=['POST'])
def auth_token():
    dados = request.get_json(silent=True) or {}
    token = dados.get('idToken')
    if not token:
        return jsonify({'status': 'error', 'message': 'Token não fornecido.'}), 400

    try:
        try:
            decoded_token = firebase_auth.verify_id_token(token)
        except Exception as e:
            # Se der o erro de relógio desajustado, espera 8 segundos e tenta de novo
            if "too early" in str(e).lower():
                time.sleep(8)
                decoded_token = firebase_auth.verify_id_token(token)
            else:
                raise e # Se for outro erro, repassa pra frente
                
        email_usuario = decoded_token.get('email', '').lower()
        
        user_ref = db.collection('usuarios').document(email_usuario)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({'status': 'error', 'message': 'Acesso negado.'}), 403
            
        user_data = user_doc.to_dict() or {}
        if not user_data.get('ativo', True):
            return jsonify({'status': 'bloqueado', 'message': 'Usuário desativado.'}), 403

        nome_completo = user_data.get('nome', decoded_token.get('name', 'Usuário')).title()
        partes_nome = nome_completo.split()
        nome_exibicao = f"{partes_nome[0]} {partes_nome[-1]}" if len(partes_nome) > 1 else partes_nome[0]

        session.permanent = True 
        session['user_id'] = decoded_token['uid']
        session['user_email'] = email_usuario
        session['user_nome'] = nome_exibicao
        session['user_filial'] = user_data.get('filial', 'Matriz')
        session['user_perfil'] = user_data.get('perfil', 'Corretor')
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 401

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/bloqueado')
def bloqueado():
    return render_template('bloqueado.html')

@auth_bp.before_app_request
def bloquear_rotas():
    session.modified = True 
    # Atualizado para a nova rota 'auth_token'
    rotas_livres = ['auth.login', 'auth.auth_token', 'static', 'auth.bloqueado']
    
    if request.endpoint and request.endpoint not in rotas_livres:
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
            
        email = session.get('user_email')
        agora = time.time()
        
        if email:
            if email not in MEMORIA_CACHE:
                MEMORIA_CACHE[email] = {}
                
            if (agora - MEMORIA_CACHE[email].get('tempo_status', 0)) > 60:
                user_doc = db.collection('usuarios').document(email).get()
                if user_doc.exists:
                    dados = user_doc.to_dict() or {}
                    MEMORIA_CACHE[email]['ativo'] = dados.get('ativo', False)
                    MEMORIA_CACHE[email]['tempo_status'] = agora
                else:
                    MEMORIA_CACHE[email]['ativo'] = False
                    MEMORIA_CACHE[email]['tempo_status'] = agora
            
            if not MEMORIA_CACHE[email].get('ativo'):
                session.clear()
                return render_template('bloqueado.html')