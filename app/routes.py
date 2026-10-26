import time
import csv
import io
import re
import pandas as pd
import calendar
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import db, MEMORIA_CACHE
from app.utils import enviar_email_boas_vindas

main_bp = Blueprint('main', __name__)

# --- CONFIGURAÇÃO DE PÁGINAS DO SISTEMA ---
PAGINAS_SISTEMA = [
    {'id': 'home', 'nome': 'Dashboard (Tela Inicial)', 'icone': 'bi-house'},
    {'id': 'visitas', 'nome': 'Visitas', 'icone': 'bi-house'},
    {'id': 'indicacao', 'nome': 'Indicação', 'icone': 'bi-house'},
    {'id': 'usuarios', 'nome': 'Gerenciar Equipe', 'icone': 'bi-people'},
    {'id': 'permissoes', 'nome': 'Matriz de Acessos', 'icone': 'bi-shield-lock'},
    {'id': 'portabilidade_interna', 'nome': 'Portabilidade Interna', 'icone': 'bi-arrow-left-right'},
    {'id': 'portabilidade_externa', 'nome': 'Portabilidade Externa', 'icone': 'bi-box-arrow-up-right'},
    {'id': 'importar_dados', 'nome': 'Importar Dados', 'icone': 'bi-box-arrow-up-right'},
    {'id': 'comissoes', 'nome': 'Relatório de Comissões', 'icone': 'bi-cash-stack'},
    {'id': 'status_visita', 'nome': 'Status das Visitas', 'icone': 'bi-calendar-check'},
]
PERFIS_SISTEMA = ['Corretor', 'Agente de Visita', 'Gerente Filial', 'Gerente Geral', 'Admin']

def registrar_log_auditoria(acao):
    # Pega quem está logado fazendo a ação
    usuario_responsavel = session.get('user_email', 'Sistema')
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    # O print manda o texto direto para a aba de Logs da Vercel
    print(f"[AUDITORIA] {agora} | RESPONSÁVEL: {usuario_responsavel} | AÇÃO: {acao}", flush=True)

@main_bp.context_processor
def injetar_dados_globais():
    # --- 1. LÓGICA DA FOTO DE PERFIL (Seu código original) ---
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

    # --- 2. LÓGICA DA MATRIZ DE ACESSOS (Novo) ---
    perfil = session.get('user_perfil', 'Corretor')
    acessos = MEMORIA_CACHE.get('matriz_acessos', {}).get(perfil, [])

    # --- 3. MANDA AS DUAS VARIÁVEIS PARA O HTML ---
    return dict(current_user_foto=foto, minhas_permissoes=acessos)

@main_bp.route('/')
def home():
    return render_template('home.html')

@main_bp.route('/indica_lello')
def indica_lello():
    return render_template('indica_lello.html')

@main_bp.route('/status_visita')
def status_visita():
    # 1. Pega os dados do usuário para fazer o filtro no banco
    email_usuario = session.get('user_email')
    user_doc = db.collection('usuarios').document(email_usuario).get()
    
    # Aqui precisamos usar o Nome ou o Usuario Portal, dependendo de como está no seu banco.
    # Como no seu exemplo a coluna tem o nome completo ("Maria de Fátima De Jesus Dias"), 
    # vou puxar o 'nome' do cadastro. Se for outro campo, altere o .get('nome') abaixo!
    nome_cruzamento = ""
    if user_doc.exists:
        nome_cruzamento = user_doc.to_dict().get('nome', '').strip()

    # 2. Resgata os parâmetros da URL
    mes_args = request.args.get('mes')
    ano_args = request.args.get('ano')
    
    visitas = []
    
    # Se não tem filtros ainda na URL (entrou na página pela primeira vez)
    if not mes_args or not ano_args:
        hoje = datetime.now()
        mes_padrao = hoje.month - 1 if hoje.month > 1 else 12
        ano_padrao = hoje.year if hoje.month > 1 else hoje.year - 1
        
        return render_template('status_visita.html',
                               mes_selecionado=mes_padrao,
                               ano_selecionado=ano_padrao,
                               buscou=False,
                               visitas=[])

    # --- Se ele clicou em consultar ---
    mes_selecionado = int(mes_args)
    ano_selecionado = int(ano_args)

    # A data do seu banco vem como "20/10/2026 15:00", então buscar "/10/2026" funciona perfeitamente!
    str_busca_br = f"/{mes_selecionado:02d}/{ano_selecionado}"
    
    # Set para impedir que o mesmo ID de Visita apareça duplicado na tela
    visitas_unicas = set()

    if nome_cruzamento:
        # ATENÇÃO 1: Coloque o nome real da tabela no Firestore no lugar de 'NOME_DA_SUA_TABELA_AQUI'
        # ATENÇÃO 2: A coluna filtro estou usando 'Atendente_Colaborador'. Você também pode usar 'Nome_Responsavel_Colaborador'
        docs = db.collection('dt_visita_periodo_agendamento').where('Nome_Responsavel_Colaborador', '==', nome_cruzamento).stream()
        
        for doc in docs:
            dados = doc.to_dict() or {}
            
            # Pega a nova coluna de data informada
            data_raw = str(dados.get('Data_Agendamento', '')).strip()
            
            # Filtro de Data
            if str_busca_br in data_raw:
                
                # Identificador Único da Visita
                id_visita = str(dados.get('Id_Visita', '')).strip()
                
                # Trava de Duplicidade
                if id_visita and id_visita in visitas_unicas:
                    continue
                    
                if id_visita and id_visita.lower() not in ['nan', 'none']:
                    visitas_unicas.add(id_visita)
                
                # Alimentando a lista pro HTML usando as chaves exatas do seu banco
                visitas.append({
                    'codigo': id_visita,
                    'tipo_imovel': dados.get('Tipo_Apartamento', 'Imóvel Genérico').title(),
                    'bairro': dados.get('Bairro', 'Bairro não informado').title(),
                    'data_formatada': data_raw,  # Vai mandar ex: "20/10/2026 15:00"
                    'status': dados.get('Status', 'Agendada').title()
                })
                
    # Ordena as visitas para ficarem empilhadas da mais recente para a mais antiga pela data
    visitas = sorted(visitas, key=lambda k: k['data_formatada'], reverse=True)

    return render_template('status_visita.html',
                           mes_selecionado=mes_selecionado,
                           ano_selecionado=ano_selecionado,
                           buscou=True,
                           visitas=visitas)

@main_bp.route('/portabilidade_interna')
def portabilidade_interna():
    return render_template('portabilidade_interna.html')

@main_bp.route('/portabilidade_externa')
def portabilidade_externa():
    return render_template('portabilidade_externa.html')


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
    perfil_logado = session.get('user_perfil')
    
    # NOVO: Agora permite Admin, Gerente Filial E Gerente Geral
    if perfil_logado not in ['Admin', 'Gerente Filial', 'Gerente Geral']:
        flash('Acesso negado.', 'floating_danger')
        return redirect(url_for('main.home'))

    # --- ADICIONAR NOVO USUÁRIO ---
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        nome = request.form.get('nome', '').strip()
        enviar_email = request.form.get('enviar_email') 
        
        # PEGA OS NOVOS CAMPOS
        usuario_portal = request.form.get('usuario_portal', '').strip()
        id_apple = request.form.get('id_apple', '').strip()

        # REGRAS DE GERÊNCIA (Trava segurança de cadastro)
        if perfil_logado in ['Gerente Filial', 'Gerente Geral']:
            if perfil_logado == 'Gerente Filial':
                filial = session.get('user_filial') # Força a ser a mesma filial dele
            else:
                filial = request.form.get('filial', '').strip() # Ger. Geral escolhe a filial

            perfil = request.form.get('perfil', 'Corretor').strip()
            
            # Gerente Filial não pode criar chefes
            if perfil_logado == 'Gerente Filial' and perfil in ['Admin', 'Gerente Geral', 'Gerente Filial']:
                perfil = 'Corretor'
            # Gerente Geral pode criar Ger. Filial, mas não Admin
            elif perfil_logado == 'Gerente Geral' and perfil == 'Admin':
                perfil = 'Corretor'
        else:
            filial = request.form.get('filial', '').strip()
            perfil = request.form.get('perfil', '').strip()

        user_ref = db.collection("usuarios").document(email)

        if user_ref.get().exists:
            flash(f'Erro: O e-mail {email} já está cadastrado no sistema!', 'danger')
            return redirect(url_for('main.usuarios'))

        dados_usuario = {
            "nome": nome, "email": email, "filial": filial,
            "perfil": perfil, "ativo": True, "nome_exibicao": nome,
            "usuario_portal": usuario_portal, "id_apple": id_apple
        }
        user_ref.set(dados_usuario)
        
        if enviar_email == 'sim':
            enviar_email_boas_vindas(email, nome, perfil)
            
        registrar_log_auditoria(f"CADASTROU o colaborador {email} ({perfil})")
        MEMORIA_CACHE.pop('lista_usuarios', None)
        flash(f'Usuário {nome} adicionado com sucesso!', 'success')
        return redirect(url_for('main.usuarios'))

    # --- CARREGAMENTO OTIMIZADO ---
    if 'lista_usuarios' in MEMORIA_CACHE:
        todos_usuarios = MEMORIA_CACHE['lista_usuarios']
    else:
        todos_usuarios = []
        docs = db.collection('usuarios').stream()
        for doc in docs:
            user_data = doc.to_dict()
            if 'email' not in user_data: user_data['email'] = doc.id
            todos_usuarios.append(user_data)
        MEMORIA_CACHE['lista_usuarios'] = todos_usuarios

    # --- LÓGICA DE FILTROS ---
    search_query = request.args.get('search', '').lower()
    perfil_filter = request.args.get('perfil', '')
    status_filter = request.args.get('status', 'ativo')
    
    # REGRAS DO GERENTE DE FILIAL (Filtro forçado)
    if perfil_logado == 'Gerente Filial':
        filial_filter = session.get('user_filial')
    else:
        filial_filter = request.args.get('filial', '')

    usuarios_online = MEMORIA_CACHE.get('online_users', {})
    agora = time.time()

    lista_usuarios = []
    for user_data in todos_usuarios:
        is_ativo = user_data.get('ativo', False)

        if status_filter == 'ativo' and not is_ativo: continue
        if status_filter == 'inativo' and is_ativo: continue
        if filial_filter and user_data.get('filial') != filial_filter: continue
        if perfil_filter and user_data.get('perfil') != perfil_filter: continue
        if search_query:
            if search_query not in str(user_data.get('nome', '')).lower() and search_query not in str(user_data.get('email', '')).lower():
                continue

        email_usuario = user_data.get('email', '')
        dados_acesso = usuarios_online.get(email_usuario, {'tempo': 0, 'dispositivo': 'computador'})
        if isinstance(dados_acesso, float): dados_acesso = {'tempo': dados_acesso, 'dispositivo': 'computador'}
            
        user_data['is_online'] = (agora - dados_acesso.get('tempo', 0)) < 600
        user_data['dispositivo'] = dados_acesso.get('dispositivo', 'computador')
        lista_usuarios.append(user_data)
        
    # Ordena a lista
    lista_usuarios = sorted(lista_usuarios, key=lambda x: x.get('nome', ''))
    current_filters = {'search': search_query, 'filial': filial_filter, 'perfil': perfil_filter, 'status': status_filter}
    
    # --- LÓGICA DE PAGINAÇÃO (EM MEMÓRIA) ---
    page = request.args.get('page', 1, type=int)
    por_pagina = 10
    total_usuarios = len(lista_usuarios)
    total_paginas = (total_usuarios + por_pagina - 1) // por_pagina
    
    # Calcula onde começa e onde termina o "corte" da lista
    inicio = (page - 1) * por_pagina
    fim = inicio + por_pagina
    
    # Fatiando a lista (pega só os 10 da página atual)
    lista_paginada = lista_usuarios[inicio:fim]
    
    return render_template('usuarios.html', 
                           lista_usuarios=lista_paginada, 
                           current_filters=current_filters,
                           page=page,
                           total_paginas=total_paginas)

@main_bp.route('/editar_usuario', methods=['POST'])
def editar_usuario():
    perfil_logado = session.get('user_perfil')
    email_logado = session.get('user_email') # Identifica quem está clicando
    
    if perfil_logado not in ['Admin', 'Gerente Filial', 'Gerente Geral']: 
        return redirect(url_for('main.home'))
    
    email_original = request.form.get('email_original', '').strip().lower()
    novo_email = request.form.get('email', '').strip().lower()
    nome = request.form.get('nome', '').strip()
    nome_exibicao = request.form.get('nome_exibicao', '').strip()
    ativo = request.form.get('ativo') == 'true'
    foto = request.form.get('foto', '').strip()
    # PEGA OS NOVOS CAMPOS
    usuario_portal = request.form.get('usuario_portal', '').strip()
    id_apple = request.form.get('id_apple', '').strip()

    is_self = (email_original == email_logado)

    # REGRAS DE GERÊNCIA (Edição)
    if perfil_logado in ['Gerente Filial', 'Gerente Geral']:
        
        # Gerente Filial é travado na própria filial. Gerente Geral pode mudar.
        if perfil_logado == 'Gerente Filial':
            filial = session.get('user_filial')
        else:
            filial = request.form.get('filial', '').strip()
            
        # Se ele estiver editando a si mesmo, TRAVA o e-mail e o perfil originais
        if is_self:
            novo_email = email_original
            perfil = perfil_logado
        else:
            perfil = request.form.get('perfil', '').strip()
            
            # Impede Gerente Filial de dar cargo de chefe
            if perfil_logado == 'Gerente Filial' and perfil in ['Admin', 'Gerente Geral', 'Gerente Filial']:
                perfil = 'Corretor'
            # Impede Gerente Geral de criar um Admin
            elif perfil_logado == 'Gerente Geral' and perfil == 'Admin':
                perfil = 'Corretor'
    else:
        # Aqui cai o Admin, que pode tudo
        filial = request.form.get('filial', '').strip()
        perfil = request.form.get('perfil', '').strip()

    user_ref = db.collection("usuarios").document(email_original)
    doc = user_ref.get()

    if doc.exists:
        dados_atuais = doc.to_dict() or {}
        
        # Bloqueia Gerente Filial de tentar editar alguém de outra filial
        if perfil_logado == 'Gerente Filial' and dados_atuais.get('filial') != session.get('user_filial'):
            flash('Erro de segurança: Acesso negado a outras filiais.', 'floating_danger')
            return redirect(url_for('main.usuarios'))

        # Trava do Status! Se for ele mesmo, força a manter o status atual do banco.
        if is_self and perfil_logado != 'Admin':
            ativo = dados_atuais.get('ativo', True)

        if novo_email != email_original:
            if db.collection("usuarios").document(novo_email).get().exists:
                flash(f'O e-mail {novo_email} já está em uso!', 'floating_danger')
                return redirect(url_for('main.usuarios'))
            dados = doc.to_dict() or {}
            dados.update({
                "nome": nome, "nome_exibicao": nome_exibicao, 
                "email": novo_email, "filial": filial, 
                "perfil": perfil, "ativo": ativo, "foto": foto,
                "usuario_portal": usuario_portal, "id_apple": id_apple
            })
            db.collection("usuarios").document(novo_email).set(dados)
            user_ref.delete()
        else:
            user_ref.update({
                "nome": nome, "nome_exibicao": nome_exibicao, 
                "filial": filial, "perfil": perfil, 
                "ativo": ativo, "foto": foto,
                "usuario_portal": usuario_portal, "id_apple": id_apple
            })
            
        registrar_log_auditoria(f"EDITOU os dados do colaborador {novo_email}")
        MEMORIA_CACHE.pop('lista_usuarios', None)
        flash('Dados atualizados com sucesso!', 'floating_success')
        
    return redirect(url_for('main.usuarios'))

# NOVA ROTA: Reenviar Convite
@main_bp.route('/reenviar_convite', methods=['POST'])
def reenviar_convite():
    if session.get('user_perfil') != 'Admin': return redirect(url_for('main.home'))
    
    email = request.form.get('email_original', '').strip().lower()
    nome = request.form.get('nome', '').strip()
    perfil = request.form.get('perfil', '').strip()

    if email and nome and perfil:
        enviar_email_boas_vindas(email, nome, perfil)
        flash(f'E-mail de convite reenviado para {email} com sucesso!', 'success')
    else:
        flash('Erro ao reenviar convite: dados incompletos.', 'danger')
        
    return redirect(url_for('main.usuarios'))

@main_bp.route('/excluir_usuario', methods=['POST'])
def excluir_usuario():
    if session.get('user_perfil') != 'Admin': return redirect(url_for('main.home'))
    email = request.form.get('email_original', '').strip().lower()

    registrar_log_auditoria(f"EXCLUIU o colaborador {email}")
    db.collection("usuarios").document(email).delete()
    if email in MEMORIA_CACHE: del MEMORIA_CACHE[email]
    
    # Força o painel a recarregar a lista nova do Firebase
    MEMORIA_CACHE.pop('lista_usuarios', None)
    
    flash('Colaborador removido!', 'success')
    return redirect(url_for('main.usuarios'))



@main_bp.route('/visitas')
def visitas():
    # 1. Pega os dados do usuário logado para descobrir o usuario_portal
    email_usuario = session.get('user_email')
    user_doc = db.collection('usuarios').document(email_usuario).get()
    usuario_portal = ""
    if user_doc.exists:
        usuario_portal = user_doc.to_dict().get('usuario_portal', '').strip()

    # 2. Lógica de Datas (Padrão: Mês Anterior)
    hoje = datetime.now()
    mes_padrao = hoje.month - 1 if hoje.month > 1 else 12
    ano_padrao = hoje.year if hoje.month > 1 else hoje.year - 1
    
    mes_selecionado = int(request.args.get('mes', mes_padrao))
    ano_selecionado = int(request.args.get('ano', ano_padrao))
    
    ultimo_dia = calendar.monthrange(ano_selecionado, mes_selecionado)[1]
    periodo_str = f"Período 01 a {ultimo_dia:02d}/{mes_selecionado:02d}/{ano_selecionado}"
    
    mes_pagamento = mes_selecionado + 1 if mes_selecionado < 12 else 1
    ano_pagamento = ano_selecionado if mes_selecionado < 12 else ano_selecionado + 1
    data_pagamento_str = f"10/{mes_pagamento:02d}/{ano_pagamento}"

    # 3. Lógica de Cálculo de Valores
    contratos_unicos = set()
    valor_total_fechado = 0.0
    
    if usuario_portal:
        docs = db.collection('dt_ctrl_pagamento_visita').where('Colaborador', '==', usuario_portal).stream()
        
        str_busca_br = f"/{mes_selecionado:02d}/{ano_selecionado}"
        str_busca_us = f"{ano_selecionado}-{mes_selecionado:02d}"
        
        for doc in docs:
            dados = doc.to_dict() or {}
            data_referencia = str(dados.get('Negocio_Data_status', ''))
            
            if str_busca_br in data_referencia or str_busca_us in data_referencia:
                
                contrato = str(dados.get('Negocio_Contrato', '')).strip()
                
                # A TRAVA DE DUPLICIDADE: Se o contrato já foi computado antes, pula pro próximo registro!
                if contrato and contrato in contratos_unicos:
                    continue
                
                # Se for um contrato novo, adiciona na lista de únicos
                if contrato and contrato.lower() not in ['nan', 'none']:
                    contratos_unicos.add(contrato)
                
                # Faz o tratamento do valor e soma (agora apenas 1 vez por contrato)
                valor_raw = str(dados.get('Negocio_Valor_fechado', '0'))
                try:
                    valor_raw = valor_raw.replace('R$', '').strip()
                    if '.' in valor_raw and ',' in valor_raw:
                        valor_clean = float(valor_raw.replace('.', '').replace(',', '.'))
                    elif ',' in valor_raw:
                        valor_clean = float(valor_raw.replace(',', '.'))
                    else:
                        valor_clean = float(valor_raw)
                except:
                    valor_clean = 0.0
                    
                valor_total_fechado += valor_clean

    # 4. Aplica a comissão de 20%
    valor_ganho = valor_total_fechado * 0.20
    
    # Formatação visual final para reais
    valor_ganho_formatado = f"{valor_ganho:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    return render_template('visitas.html', 
                           mes_selecionado=mes_selecionado, 
                           ano_selecionado=ano_selecionado,
                           periodo_str=periodo_str,
                           data_pagamento_str=data_pagamento_str,
                           total_contratos=len(contratos_unicos),
                           valor_ganho_formatado=valor_ganho_formatado)

@main_bp.route('/simular_acesso', methods=['POST'])
def simular_acesso():
    if session.get('user_perfil') != 'Admin' and not session.get('admin_original'):
        return redirect(url_for('main.home'))

    email_alvo = request.form.get('email_alvo', '').strip().lower()
    
    user_doc = db.collection('usuarios').document(email_alvo).get()
    if not user_doc.exists:
        flash('Usuário não encontrado.', 'danger')
        registrar_log_auditoria(f"Iniciou a SIMULAÇÃO DE ACESSO do usuário {email_alvo}")
        return redirect(url_for('main.usuarios'))
        
    user_data = user_doc.to_dict() or {}
    
    # Salva o seu e-mail de Admin antes de trocar a identidade, se já não estiver salvo
    if 'admin_original' not in session:
        session['admin_original'] = session.get('user_email')
        
    # Atualiza a sessão para os dados do colaborador
    session['user_email'] = email_alvo
    session['user_nome'] = user_data.get('nome_exibicao', user_data.get('nome', 'Usuário'))
    session['user_filial'] = user_data.get('filial', 'Matriz')
    session['user_perfil'] = user_data.get('perfil', 'Corretor')
    
    flash(f'Simulando o acesso de {session["user_nome"]}.', 'floating_info')
    return redirect(url_for('main.home'))

@main_bp.route('/restaurar_acesso')
def restaurar_acesso():
    admin_email = session.get('admin_original')
    if not admin_email:
        registrar_log_auditoria(f"Encerrou a simulação e RESTAUROU o acesso de Admin")
        return redirect(url_for('main.home'))
        
    user_doc = db.collection('usuarios').document(admin_email).get()
    if user_doc.exists:
        user_data = user_doc.to_dict() or {}
        session['user_email'] = admin_email
        session['user_nome'] = user_data.get('nome_exibicao', user_data.get('nome', 'Admin'))
        session['user_filial'] = user_data.get('filial', 'Matriz')
        session['user_perfil'] = user_data.get('perfil', 'Admin')
        
    session.pop('admin_original', None)
    flash('Acesso de Administrador restaurado.', 'floating_success')
    return redirect(url_for('main.usuarios'))

@main_bp.before_request
def registrar_atividade():
    if 'user_email' in session:
        if 'online_users' not in MEMORIA_CACHE:
            MEMORIA_CACHE['online_users'] = {}
            
        # Lê a "identidade" do navegador
        user_agent = request.headers.get('User-Agent', '').lower()
        is_mobile = 'mobi' in user_agent or 'android' in user_agent or 'iphone' in user_agent
        
        # O PULO DO GATO: Se estiver simulando, marca o ponto para o Admin original!
        # Se não estiver simulando, marca para o usuário logado normalmente.
        email_ativo = session.get('admin_original') if session.get('admin_original') else session['user_email']
        
        MEMORIA_CACHE['online_users'][email_ativo] = {
            'tempo': time.time(),
            'dispositivo': 'celular' if is_mobile else 'computador'
        }

        endpoint = request.endpoint
        # Só analisa se for uma rota do sistema (ignora login, imagens e css)
        if endpoint and endpoint.startswith('main.') and endpoint not in ['main.home', 'main.perfil']:
            tela_acessada = endpoint.split('.')[1] 
            
            # --- NOVO: Mapeamento de rotas de ação para a tela principal ---
            rotas_filhas = {
                'editar_usuario': 'usuarios',
                'excluir_usuario': 'usuarios',
                'simular_acesso': 'usuarios',
                'restaurar_acesso': 'usuarios'
            }
            
            # Se for uma ação (ex: editar_usuario), verifica se tem acesso à tela mãe (usuarios)
            tela_para_validar = rotas_filhas.get(tela_acessada, tela_acessada)
            
            perfil_logado = session.get('user_perfil', 'Corretor')
            
            # Se a memória estiver vazia, carrega do Firebase (1 vez)
            if 'matriz_acessos' not in MEMORIA_CACHE:
                doc = db.collection('configuracoes').document('matriz_acessos').get()
                MEMORIA_CACHE['matriz_acessos'] = doc.to_dict() if doc.exists else {}
                
            acessos_permitidos = MEMORIA_CACHE['matriz_acessos'].get(perfil_logado, ['home'])
            
            # Se a tela (ou a tela mãe) não estiver na lista dele, bloqueia!
            if tela_para_validar not in acessos_permitidos and perfil_logado != 'Admin':
                if tela_acessada == 'restaurar_acesso' and 'admin_original' in session:
                    pass # allow
                else:
                    registrar_log_auditoria(f"TENTATIVA DE INVASÃO: Bloqueado na rota '{tela_acessada}'")
                    flash(f'Acesso restrito. O seu perfil ({perfil_logado}) não tem permissão para esta ação.', 'floating_danger')
                    return redirect(url_for('main.home'))

@main_bp.route('/permissoes', methods=['GET', 'POST'])
def permissoes():
    # Apenas o Admin Supremo pode mexer aqui
    if session.get('user_perfil') != 'Admin':
        flash('Acesso negado. Apenas Administradores podem configurar permissões.', 'floating_danger')
        return redirect(url_for('main.home'))

    # --- SALVAR AS PERMISSÕES ---
    if request.method == 'POST':
        novas_permissoes = {}
        for perfil in PERFIS_SISTEMA:
            # Captura todos os checkboxes marcados para aquele perfil
            selecionadas = request.form.getlist(f'permissoes_{perfil}')
            novas_permissoes[perfil] = selecionadas

        # Grava no banco com 1 única gravação
        db.collection('configuracoes').document('matriz_acessos').set(novas_permissoes)
        
        # Atualiza a memória
        MEMORIA_CACHE['matriz_acessos'] = novas_permissoes
        registrar_log_auditoria("ATUALIZOU a Matriz de Acessos do sistema")
        
        flash('Permissões atualizadas com sucesso!', 'success')
        return redirect(url_for('main.permissoes'))

    # --- CARREGAR AS PERMISSÕES (USANDO CACHE) ---
    if 'matriz_acessos' not in MEMORIA_CACHE:
        doc = db.collection('configuracoes').document('matriz_acessos').get()
        if doc.exists:
            MEMORIA_CACHE['matriz_acessos'] = doc.to_dict()
        else:
            # Por padrão, se não existir nada salvo, libera tudo pro Admin e só a Home pro resto
            MEMORIA_CACHE['matriz_acessos'] = {p: ['home', 'usuarios', 'permissoes', 'comissoes'] if p == 'Admin' else ['home'] for p in PERFIS_SISTEMA}

    permissoes_atuais = MEMORIA_CACHE['matriz_acessos']

    return render_template('permissoes.html', 
                           paginas=PAGINAS_SISTEMA, 
                           perfis=PERFIS_SISTEMA, 
                           permissoes_atuais=permissoes_atuais)

@main_bp.route('/importar_usuarios', methods=['POST'])
def importar_usuarios():
    if session.get('user_perfil') != 'Admin':
        return redirect(url_for('main.home'))
        
    arquivo = request.files.get('arquivo_csv')
    if not arquivo or arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('main.usuarios'))
        
    try:
        # Lê o conteúdo do arquivo
        stream = io.StringIO(arquivo.stream.read().decode("UTF8", errors='ignore'), newline=None)
        
        # O Excel no Brasil costuma separar por ponto-e-vírgula (;) em vez de vírgula (,)
        try:
            dialect = csv.Sniffer().sniff(stream.read(1024))
            stream.seek(0)
            csv_reader = csv.DictReader(stream, dialect=dialect)
        except:
            stream.seek(0)
            csv_reader = csv.DictReader(stream, delimiter=';') # Tenta ponto-e-vírgula como fallback
        
        cadastrados = 0
        
        for row in csv_reader:
            # Puxa o cabeçalho ignorando espaços e letras maiúsculas
            row_lower = {k.strip().lower() if k else '': v for k, v in row.items()}
            
            email = row_lower.get('email', '').strip().lower()
            if not email:
                continue # Pula linhas vazias
                
            nome = row_lower.get('nome', '').strip()
            filial = row_lower.get('filial', '(10) Centro Adm.').strip()
            perfil = row_lower.get('perfil', 'Corretor').strip()
            
            # NOVO: Lê a coluna de e-mail (por segurança, se deixarem em branco, o padrão é 'nao')
            enviar_email = row_lower.get('enviar_email', 'nao').strip().lower()
            
            user_ref = db.collection("usuarios").document(email)
            
            # Só cadastra se o e-mail não existir no banco
            if not user_ref.get().exists:
                user_ref.set({
                    "nome": nome,
                    "nome_exibicao": nome,
                    "email": email,
                    "filial": filial,
                    "perfil": perfil,
                    "ativo": True
                })
                
                # O PULO DO GATO: Dispara o e-mail SÓ se a linha atual pedir!
                if enviar_email == 'sim':
                    enviar_email_boas_vindas(email, nome, perfil)
                
                cadastrados += 1
                
        # Limpa o cache para a tela mostrar os novos usuários
        MEMORIA_CACHE.pop('lista_usuarios', None)
        registrar_log_auditoria(f"IMPORTOU em massa {cadastrados} colaboradores via CSV")
        
        flash(f'Importação concluída! {cadastrados} usuários novos adicionados com sucesso.', 'success')
        
    except Exception as e:
        flash(f'Erro ao processar o arquivo CSV. Verifique se ele está no formato correto. Detalhe: {str(e)}', 'danger')
        
    return redirect(url_for('main.usuarios'))

@main_bp.route('/importar_dados', methods=['GET', 'POST'])
def importar_dados():
    # Apenas Admin deve ter permissão para criar coleções e fazer cargas em massa
    if session.get('user_perfil') != 'Admin':
        flash('Acesso negado. Apenas Administradores podem importar dados.', 'floating_danger')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        arquivo = request.files.get('arquivo_excel')
        if not arquivo or arquivo.filename == '':
            flash('Nenhum arquivo selecionado.', 'floating_danger')
            return redirect(url_for('main.importar_dados'))

        # Lógica de seleção da coleção (tabela)
        colecao_destino = request.form.get('colecao_destino')
        nova_colecao = request.form.get('nova_colecao','').strip()

        colecao_final = nova_colecao if colecao_destino == 'nova' else colecao_destino

        if not colecao_final:
            flash('Você precisa selecionar ou digitar o nome de uma tabela destino.', 'floating_danger')
            return redirect(url_for('main.importar_dados'))

        try:
            df = pd.read_excel(arquivo)
            df = df.fillna('')
            registros = df.to_dict(orient='records')
            
            coluna_id = request.form.get('coluna_id', '').strip()
            
            # 1. Busca todos os IDs que JÁ EXISTEM na tabela destino
            ids_existentes = set()
            if coluna_id:
                # O .select([]) traz APENAS o ID dos documentos, sem os dados, deixando a consulta super rápida
                docs = db.collection(colecao_final).select([]).stream()
                for doc in docs:
                    ids_existentes.add(doc.id)

            batch = db.batch()
            contador_novos = 0
            contador_ignorados = 0
            
            for reg in registros:
                if coluna_id and coluna_id in reg:
                    doc_id = str(reg[coluna_id]).strip()
                    
                    if not doc_id:
                        continue
                        
                    # 2. A MÁGICA: Se o ID da planilha já existir no banco, ele pula para a próxima linha
                    if doc_id in ids_existentes:
                        contador_ignorados += 1
                        continue
                        
                    doc_ref = db.collection(colecao_final).document(doc_id)
                else:
                    # Se não informou coluna de ID, gera um ID aleatório
                    doc_ref = db.collection(colecao_final).document()
                
                # 3. Salva apenas os registros que passaram no filtro
                batch.set(doc_ref, reg)
                contador_novos += 1
                
                if contador_novos > 0 and contador_novos % 500 == 0:
                    batch.commit()
                    batch = db.batch()
            
            # Comita o restante
            if contador_novos % 500 != 0:
                batch.commit()

            registrar_log_auditoria(f"IMPORTOU {contador_novos} novos registros para '{colecao_final}' (Ignorou {contador_ignorados} repetidos)")
            
            if contador_ignorados > 0:
                flash(f'Sucesso! {contador_novos} novos cadastros importados. {contador_ignorados} repetidos foram ignorados.', 'floating_info')
            else:
                flash(f'Sucesso! {contador_novos} linhas foram importadas na tabela "{colecao_final}".', 'floating_success')

        except Exception as e:
            flash(f'Erro ao processar o arquivo Excel: {str(e)}', 'floating_danger')
            
        return redirect(url_for('main.importar_dados'))

    # Método GET: Pega a lista de tabelas existentes para popular o dropdown
    colecoes_firebase = [colecao.id for colecao in db.collections()]
    return render_template('importar_dados.html', colecoes=colecoes_firebase)


# ============================================================================
# RELATÓRIO DE COMISSÕES
# ============================================================================
@main_bp.route('/comissoes', methods=['GET'])
def comissoes():
    perfil_logado = session.get('user_perfil')
    email_logado = session.get('user_email')
    filial_logada = session.get('user_filial')

    # --- Regras de acesso por perfil ---
    pode_ver_todos = perfil_logado in ['Admin', 'Gerente Geral']
    gerente_filial = perfil_logado == 'Gerente Filial'
    e_corretor = perfil_logado in ['Corretor', 'Agente de Visita']

    if not (pode_ver_todos or gerente_filial or e_corretor):
        flash('Acesso negado. Você não tem permissão para visualizar relatórios de comissões.', 'floating_danger')
        return redirect(url_for('main.home'))

    # --- Filtros de período ---
    hoje = datetime.now()
    mes_padrao = hoje.month - 1 if hoje.month > 1 else 12
    ano_padrao = hoje.year if hoje.month > 1 else hoje.year - 1

    mes_selecionado = int(request.args.get('mes', mes_padrao))
    ano_selecionado = int(request.args.get('ano', ano_padrao))

    ultimo_dia = calendar.monthrange(ano_selecionado, mes_selecionado)[1]
    str_busca_br = f"/{mes_selecionado:02d}/{ano_selecionado}"
    str_busca_us = f"{ano_selecionado}-{mes_selecionado:02d}"

    # --- Filtro de filial e corretor ---
    filial_filtro = request.args.get('filial', '').strip()
    corretor_filtro = request.args.get('corretor', '').strip()

    if e_corretor:
        # Corretor vê apenas o próprio usuario_portal
        user_doc = db.collection('usuarios').document(email_logado).get()
        usuario_portal_meu = user_doc.to_dict().get('usuario_portal', '') if user_doc.exists else ''
        colaboradores = [usuario_portal_meu] if usuario_portal_meu else []
        filial_filtro = filial_logada
    elif gerente_filial:
        # Gerente Filial só vê corretores da própria filial
        filial_filtro = filial_logada
        colaboradores = None  # será preenchido abaixo
    else:
        # Admin / Gerente Geral: filtro opcional
        colaboradores = None

    # --- Carregar lista de corretores elegíveis (para dropdown e iteração) ---
    usuarios_query = db.collection('usuarios').where('perfil', '==', 'Corretor').where('ativo', '==', True).stream()
    todos_corretores = []
    for doc in usuarios_query:
        dados = doc.to_dict() or {}
        dados['email'] = doc.id
        if gerente_filial and dados.get('filial') != filial_logada:
            continue
        if filial_filtro and dados.get('filial') != filial_filtro:
            continue
        todos_corretores.append(dados)

    # Determinar lista de colaboradores (usuario_portal) a consultar
    if colaboradores is None:
        colaboradores = [c.get('usuario_portal', '') for c in todos_corretores if c.get('usuario_portal')]

    # --- Mapear email -> dados do corretor para exibição ---
    mapa_corretor = {c.get('usuario_portal'): c for c in todos_corretores}

    # --- Consultar comissões por colaborador ---
    resultados = []
    total_contratos_geral = 0
    valor_fechado_geral = 0.0
    comissao_geral = 0.0

    for portal in colaboradores:
        if not portal:
            continue
        docs = db.collection('dt_ctrl_pagamento_visita').where('Colaborador', '==', portal).stream()

        contratos_unicos = set()
        valor_total_fechado = 0.0

        for doc in docs:
            dados = doc.to_dict() or {}
            data_referencia = str(dados.get('Negocio_Data_status', ''))

            if str_busca_br not in data_referencia and str_busca_us not in data_referencia:
                continue

            contrato = str(dados.get('Negocio_Contrato', '')).strip()
            if contrato and contrato in contratos_unicos:
                continue
            if contrato and contrato.lower() not in ['nan', 'none']:
                contratos_unicos.add(contrato)

            valor_raw = str(dados.get('Negocio_Valor_fechado', '0'))
            try:
                valor_raw = valor_raw.replace('R$', '').strip()
                if '.' in valor_raw and ',' in valor_raw:
                    valor_clean = float(valor_raw.replace('.', '').replace(',', '.'))
                elif ',' in valor_raw:
                    valor_clean = float(valor_raw.replace(',', '.'))
                else:
                    valor_clean = float(valor_raw)
            except Exception:
                valor_clean = 0.0

            valor_total_fechado += valor_clean

        if not contratos_unicos:
            continue

        valor_ganho = valor_total_fechado * 0.20
        info = mapa_corretor.get(portal, {})
        resultados.append({
            'nome': info.get('nome', portal),
            'email': info.get('email', ''),
            'filial': info.get('filial', ''),
            'total_contratos': len(contratos_unicos),
            'valor_fechado': valor_total_fechado,
            'comissao': valor_ganho,
        })

        total_contratos_geral += len(contratos_unicos)
        valor_fechado_geral += valor_total_fechado
        comissao_geral += valor_ganho

    # Ordenar por nome
    resultados.sort(key=lambda x: x.get('nome', ''))

    # Lista de filiais para o dropdown (só Admin/Gerente)
    filiais_disponiveis = []
    if pode_ver_todos or gerente_filial:
        filiais_set = set()
        for c in todos_corretores:
            if c.get('filial'):
                filiais_set.add(c.get('filial'))
        filiais_disponiveis = sorted(filiais_set)

    meses = [(1, 'Janeiro'), (2, 'Fevereiro'), (3, 'Março'), (4, 'Abril'), (5, 'Maio'), (6, 'Junho'),
             (7, 'Julho'), (8, 'Agosto'), (9, 'Setembro'), (10, 'Outubro'), (11, 'Novembro'), (12, 'Dezembro')]
    anos = [2024, 2025, 2026]

    def fmt_brl(valor):
        return f"{valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    return render_template('comissoes.html',
                           resultados=resultados,
                           total_contratos_geral=total_contratos_geral,
                           valor_fechado_geral=valor_fechado_geral,
                           comissao_geral=comissao_geral,
                           mes_selecionado=mes_selecionado,
                           ano_selecionado=ano_selecionado,
                           meses=meses,
                           anos=anos,
                           corretor_filtro=corretor_filtro,
                           filial_filtro=filial_filtro,
                           filiais_disponiveis=filiais_disponiveis,
                           pode_ver_todos=pode_ver_todos,
                           e_corretor=e_corretor,
                           fmt_brl=fmt_brl,
                           periodo_str=f"01 a {ultimo_dia:02d}/{mes_selecionado:02d}/{ano_selecionado}")