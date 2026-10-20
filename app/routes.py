import time
import csv
import io
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
            "perfil": perfil, "ativo": True, "nome_exibicao": nome
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
                "perfil": perfil, "ativo": ativo, "foto": foto
            })
            db.collection("usuarios").document(novo_email).set(dados)
            user_ref.delete()
        else:
            user_ref.update({
                "nome": nome, "nome_exibicao": nome_exibicao, 
                "filial": filial, "perfil": perfil, 
                "ativo": ativo, "foto": foto
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
            MEMORIA_CACHE['matriz_acessos'] = {p: ['home', 'usuarios', 'permissoes'] if p == 'Admin' else ['home'] for p in PERFIS_SISTEMA}

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