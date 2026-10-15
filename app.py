from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import firebase_admin
import time
from firebase_admin import credentials, firestore, auth

MEMORIA_CACHE = {}

app = Flask(__name__)
app.secret_key = 'AIzaSyA4WPItplXhSjkEP9P9tx_XMNijrbd89XY'

# 1. Conexão com o Firebase Admin (Usando sua chave privada JSON)
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# --- ROTAS DE AUTENTICAÇÃO COM GOOGLE ---

@app.route('/login')
def login():
    # Se o usuário já estiver com a sessão ativa, manda direto pra Home!
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    return render_template('login.html')

@app.route('/auth_google', methods=['POST'])
def auth_google():
    token = request.json.get('idToken')
    try:
        decoded_token = auth.verify_id_token(token)
        email_google = decoded_token.get('email', '').lower()
        
        # 1. VERIFICA SE O USUÁRIO FOI CONVIDADO (Existe no banco)
        # O ID do documento do usuário será o próprio e-mail dele
        user_ref = db.collection('usuarios').document(email_google)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({'status': 'error', 'message': 'Acesso negado: Seu e-mail não tem permissão para acessar o sistema.'}), 403
            
        # Adicionamos "or {}" para o Pylance ter certeza que é um dicionário
        user_data = user_doc.to_dict() or {}
        
        if not user_data.get('ativo', True):
            return jsonify({'status': 'error', 'message': 'Acesso negado: Seu usuário foi desativado.'}), 403

        # 2. FORMATAR O NOME PARA EXIBIÇÃO
        # Pega o nome do banco. Se for "ROBERTTY DENYLLOW BASILIO DE ALMEIDA", converte para "Robertty Almeida"
        nome_completo = user_data.get('nome', decoded_token.get('name', 'Usuário')).title()
        partes_nome = nome_completo.split()
        nome_exibicao = f"{partes_nome[0]} {partes_nome[-1]}" if len(partes_nome) > 1 else partes_nome[0]

        # 3. SALVAR INFORMAÇÕES NA SESSÃO DO SISTEMA
        session['user_id'] = decoded_token['uid']
        session['user_email'] = email_google
        session['user_nome'] = nome_exibicao
        session['user_filial'] = user_data.get('filial', 'Matriz')
        session['user_perfil'] = user_data.get('perfil', 'Corretor')
        
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- BLOQUEIO DE ROTAS ---
@app.before_request
def bloquear_rotas():
    rotas_livres = ['login', 'auth_google', 'static']
    if request.endpoint not in rotas_livres and 'user_id' not in session:
        return redirect(url_for('login'))

# --- ROTAS DO SISTEMA ---

@app.route('/')
def home():
    return render_template('home.html')

@app.context_processor
def injetar_dados_usuario():
    foto = ''
    if 'user_email' in session:
        email = session['user_email']
        agora = time.time()
        
        # Verifica se a foto está no cache e tem menos de 10 minutos (600 segundos)
        if email in MEMORIA_CACHE and (agora - MEMORIA_CACHE[email]['tempo']) < 600:
            foto = MEMORIA_CACHE[email]['foto']
        else:
            # Se não tem no cache (ou passou 10 min), busca no Firebase e salva
            user_doc = db.collection('usuarios').document(email).get()
            if user_doc.exists:
                data = user_doc.to_dict() or {}  # O "or {}" resolve o aviso do Pylance!
                foto = data.get('foto', '')
                # Guarda na memória
                MEMORIA_CACHE[email] = {'foto': foto, 'tempo': agora}
                
    return dict(current_user_foto=foto)

@app.route('/indicacao')
def indicacao():
    return render_template('indicacao.html')

@app.route('/perfil', methods=['GET', 'POST'])
def perfil():
    email_usuario = session.get('user_email')
    user_ref = db.collection('usuarios').document(email_usuario)
    
    # 1. Quando o botão "Salvar Alterações" é clicado (POST)
    if request.method == 'POST':
        novo_nome_exibicao = request.form.get('nome_exibicao')
        foto_b64 = request.form.get('foto_base64') # Agora o Pylance reconhece!
        
        updates = {}
        if novo_nome_exibicao:
            updates['nome_exibicao'] = novo_nome_exibicao
            session['user_nome'] = novo_nome_exibicao
            session['user_foto'] = foto_b64
            
        # O uso do foto_b64 deve estar recuado junto com o if acima
        if foto_b64:
            updates['foto'] = foto_b64
            if email_usuario in MEMORIA_CACHE:
                MEMORIA_CACHE[email_usuario]['foto'] = foto_b64
                
        if updates:
            user_ref.update(updates)
            flash('Perfil atualizado com sucesso!', 'success')
            
        return redirect(url_for('perfil'))

    # 2. Quando o usuário apenas abre a página para visualizar (GET)
    user_doc = user_ref.get()
    user_data = user_doc.to_dict() or {} if user_doc.exists else {}
    
    user = {
        "nome": user_data.get('nome', session.get('user_nome')),
        "nome_exibicao": user_data.get('nome_exibicao', session.get('user_nome')),
        "email": email_usuario,
        "filial": user_data.get('filial', session.get('user_filial')),
        "id": session.get('user_id'),
        "foto": user_data.get('foto', '') 
        
    }
        
    return render_template('perfil.html', user=user)

@app.route('/visitas')
def visitas():
    agora = time.time()
    
    # Cache de 5 minutos (300 segundos). Se já lemos há pouco tempo, pega da memória!
    if 'lista_visitas' in MEMORIA_CACHE and (agora - MEMORIA_CACHE['lista_visitas']['tempo']) < 300:
        grupos = MEMORIA_CACHE['lista_visitas']['dados']
    else:
        # Só vai no Firebase se o cache expirou
        imoveis_ref = db.collection('db_visita_locacao')
        docs = imoveis_ref.stream()

        grupos = {"PENDENTE AUT.": [], "A FAZER": [], "CANCELADAS": [], "REALIZADAS": []}

        for doc in docs:
            imovel_raw = doc.to_dict() or {}
            if not imovel_raw:
                continue

            status_excel = str(imovel_raw.get('Dados_da_visita_Status', ''))
            if status_excel == 'Fazer': status = 'A FAZER'
            elif status_excel == 'Cancelada': status = 'CANCELADAS'
            elif status_excel == 'Realizada': status = 'REALIZADAS'
            else: status = 'PENDENTE AUT.'
                
            valor_raw = imovel_raw.get('Dados_do_Imovel_Valor', 0)
            if isinstance(valor_raw, str):
                try: valor_int = float(valor_raw.replace('.', '').replace(',', '.'))
                except: valor_int = 0.0
            else:
                valor_int = float(valor_raw) if valor_raw else 0.0
                
            valor_comissao = valor_int * (6.0 / 100)
            
            imovel_formatado = {
                "id_imovel": str(imovel_raw.get('Dados_do_Imovel_Codigo', 'S/N')),
                "endereco": str(imovel_raw.get('Dados_do_Imovel_Bairro', 'Imóvel')),
                "numero": "S/N",
                "bairro": str(imovel_raw.get('Dados_do_Imovel_Bairro.1', 'Não Informado')),
                "cidade": "São Paulo", "uf": "SP", "cep": "00000-000",
                "valor_int_str": f'R$ {valor_int:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
                "tipo_adm": "COM ADM", "percentual": 6.0,
                "valor_comissao_str": f'R$ {valor_comissao:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
            }
            
            if status in grupos:
                grupos[status].append(imovel_formatado)
        
        # Salva o resultado na memória para as próximas requisições
        MEMORIA_CACHE['lista_visitas'] = {'dados': grupos, 'tempo': agora}

    return render_template('visitas.html', grupos=grupos)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)