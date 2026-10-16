import time
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import db, MEMORIA_CACHE
from app.utils import enviar_email_boas_vindas

main_bp = Blueprint('main', __name__)

@main_bp.context_processor
def injetar_dados_usuario():
    foto = ''
    email = session.get('user_email')
    if email:
        agora = time.time()
        if email in MEMORIA_CACHE and (agora - MEMORIA_CACHE[email].get('tempo', 0)) < 600:
            foto = MEMORIA_CACHE[email].get('foto', '')
        else:
            user_doc = db.collection('usuarios').document(email).get()
            if user_doc.exists:
                data = user_doc.to_dict() or {}
                foto = data.get('foto', '')
                if email not in MEMORIA_CACHE:
                    MEMORIA_CACHE[email] = {}
                MEMORIA_CACHE[email]['foto'] = foto
                MEMORIA_CACHE[email]['tempo'] = agora
    return dict(current_user_foto=foto)

@main_bp.route('/')
def home():
    return render_template('home.html')

@main_bp.route('/indicacao')
def indicacao():
    return render_template('indicacao.html')

@main_bp.route('/perfil', methods=['GET', 'POST'])
def perfil():
    email_usuario = session.get('user_email')
    user_ref = db.collection('usuarios').document(email_usuario)
    
    if request.method == 'POST':
        novo_nome_exibicao = request.form.get('nome_exibicao')
        foto_b64 = request.form.get('foto_base64')
        updates = {}
        if novo_nome_exibicao:
            updates['nome_exibicao'] = novo_nome_exibicao
            session['user_nome'] = novo_nome_exibicao
        if foto_b64:
            updates['foto'] = foto_b64
            if email_usuario in MEMORIA_CACHE:
                MEMORIA_CACHE[email_usuario]['foto'] = foto_b64
        if updates:
            user_ref.update(updates)
            flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('main.perfil'))

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

@main_bp.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    if session.get('user_perfil') != 'Admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        nome = request.form.get('nome', '').strip()
        filial = request.form.get('filial', '').strip()
        perfil = request.form.get('perfil', '').strip()

        dados_usuario = {
            "nome": nome, "email": email, "filial": filial,
            "perfil": perfil, "ativo": True, "nome_exibicao": nome
        }
        db.collection("usuarios").document(email).set(dados_usuario)
        enviar_email_boas_vindas(email, nome, perfil)
        flash(f'Usuário {nome} adicionado com sucesso!', 'success')
        return redirect(url_for('main.usuarios'))

    search_query = request.args.get('search', '').lower()
    filial_filter = request.args.get('filial', '')
    perfil_filter = request.args.get('perfil', '')
    status_filter = request.args.get('status', 'ativo')

    lista_usuarios = []
    docs = db.collection('usuarios').stream()
    for doc in docs:
        user_data = doc.to_dict()
        if 'email' not in user_data: user_data['email'] = doc.id
        is_ativo = user_data.get('ativo', False)

        if status_filter == 'ativo' and not is_ativo: continue
        if status_filter == 'inativo' and is_ativo: continue
        if filial_filter and user_data.get('filial') != filial_filter: continue
        if perfil_filter and user_data.get('perfil') != perfil_filter: continue
        if search_query:
            if search_query not in str(user_data.get('nome', '')).lower() and search_query not in str(user_data.get('email', '')).lower():
                continue

        lista_usuarios.append(user_data)
        
    lista_usuarios = sorted(lista_usuarios, key=lambda x: x.get('nome', ''))
    current_filters = {'search': search_query, 'filial': filial_filter, 'perfil': perfil_filter, 'status': status_filter}
    return render_template('usuarios.html', lista_usuarios=lista_usuarios, current_filters=current_filters)

@main_bp.route('/editar_usuario', methods=['POST'])
def editar_usuario():
    if session.get('user_perfil') != 'Admin': return redirect(url_for('main.home'))
    email_original = request.form.get('email_original', '').strip().lower()
    novo_email = request.form.get('email', '').strip().lower()
    nome = request.form.get('nome', '').strip()
    nome_exibicao = request.form.get('nome_exibicao', '').strip()
    filial = request.form.get('filial', '').strip()
    perfil = request.form.get('perfil', '').strip()
    ativo = request.form.get('ativo') == 'true'

    user_ref = db.collection("usuarios").document(email_original)
    doc = user_ref.get()

    if doc.exists:
        if novo_email != email_original:
            if db.collection("usuarios").document(novo_email).get().exists:
                flash(f'O e-mail {novo_email} já está em uso!', 'danger')
                return redirect(url_for('main.usuarios'))
            dados = doc.to_dict() or {}
            dados.update({"nome": nome, "nome_exibicao": nome_exibicao, "email": novo_email, "filial": filial, "perfil": perfil, "ativo": ativo})
            db.collection("usuarios").document(novo_email).set(dados)
            user_ref.delete()
            if email_original in MEMORIA_CACHE: del MEMORIA_CACHE[email_original]
        else:
            user_ref.update({"nome": nome, "nome_exibicao": nome_exibicao, "filial": filial, "perfil": perfil, "ativo": ativo})
            if email_original not in MEMORIA_CACHE: MEMORIA_CACHE[email_original] = {}
            MEMORIA_CACHE[email_original]['ativo'] = ativo
            MEMORIA_CACHE[email_original]['tempo_status'] = time.time()
        flash(f'Dados atualizados com sucesso!', 'success')
    return redirect(url_for('main.usuarios'))

@main_bp.route('/excluir_usuario', methods=['POST'])
def excluir_usuario():
    if session.get('user_perfil') != 'Admin': return redirect(url_for('main.home'))
    email = request.form.get('email_original', '').strip().lower()
    db.collection("usuarios").document(email).delete()
    if email in MEMORIA_CACHE: del MEMORIA_CACHE[email]
    flash('Colaborador removido!', 'success')
    return redirect(url_for('main.usuarios'))

@main_bp.route('/visitas')
def visitas():
    agora = time.time()
    if 'lista_visitas' in MEMORIA_CACHE and (agora - MEMORIA_CACHE['lista_visitas']['tempo']) < 300:
        grupos = MEMORIA_CACHE['lista_visitas']['dados']
    else:
        docs = db.collection('db_visita_locacao').stream()
        grupos = {"PENDENTE AUT.": [], "A FAZER": [], "CANCELADAS": [], "REALIZADAS": []}
        for doc in docs:
            imovel_raw = doc.to_dict() or {}
            if not imovel_raw: continue
            status_excel = str(imovel_raw.get('Dados_da_visita_Status', ''))
            status = 'A FAZER' if status_excel == 'Fazer' else 'CANCELADAS' if status_excel == 'Cancelada' else 'REALIZADAS' if status_excel == 'Realizada' else 'PENDENTE AUT.'
            valor_raw = imovel_raw.get('Dados_do_Imovel_Valor', 0)
            valor_int = float(str(valor_raw).replace('.', '').replace(',', '.')) if isinstance(valor_raw, str) else float(valor_raw) if valor_raw else 0.0
            
            grupos[status].append({
                "id_imovel": str(imovel_raw.get('Dados_do_Imovel_Codigo', 'S/N')),
                "endereco": str(imovel_raw.get('Dados_do_Imovel_Bairro', 'Imóvel')),
                "numero": "S/N", "bairro": str(imovel_raw.get('Dados_do_Imovel_Bairro.1', 'Não Informado')),
                "cidade": "São Paulo", "uf": "SP", "cep": "00000-000",
                "valor_int_str": f'R$ {valor_int:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
                "tipo_adm": "COM ADM", "percentual": 6.0,
                "valor_comissao_str": f'R$ {valor_int * 0.06:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
            })
        MEMORIA_CACHE['lista_visitas'] = {'dados': grupos, 'tempo': agora}
    return render_template('visitas.html', grupos=grupos)