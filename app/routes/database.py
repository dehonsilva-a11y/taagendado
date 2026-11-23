import os
import zlib
import sqlite3
import tempfile
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOCAL_DB_PATH = os.path.join(DATA_DIR, 'dados_analiticos.db')
ENCRYPTED_DB_PATH = os.path.join(DATA_DIR, 'dados_analiticos.enc')
TMP_DB_PATH = os.path.join(tempfile.gettempdir(), 'taagendado_dados_analiticos.db')

# Esquema padrão das tabelas analíticas para garantir que nunca ocorra erro de "no such table"
TABELAS_PADRAO = {
    'Databricks_Historico': '''
        CREATE TABLE IF NOT EXISTS Databricks_Historico (
            Id_Visita TEXT,
            Id_Imovel TEXT,
            Endereco TEXT,
            Segmento TEXT,
            Data_Agendamento TEXT,
            Status_Visita TEXT,
            Resultado_Visita TEXT,
            Id_Atendimento TEXT,
            Id_gn TEXT,
            Status_gn TEXT,
            Etapa_gn TEXT,
            Colaborador_Visita TEXT
        )
    ''',
    'dt_ctrl_pagamento_visita': '''
        CREATE TABLE IF NOT EXISTS dt_ctrl_pagamento_visita (
            Colaborador TEXT,
            Negocio_Data_status TEXT,
            Data_Status TEXT,
            Gestao_Data_Status TEXT,
            Negocio_Contrato TEXT,
            Contrato_Codigo TEXT,
            Gestao_GN TEXT,
            Negocio_Valor_fechado TEXT
        )
    ''',
    'dt_gestao_negocios_finalizados': '''
        CREATE TABLE IF NOT EXISTS dt_gestao_negocios_finalizados (
            Atendimento_Colaborador_Visita TEXT,
            Negocio_Data_status TEXT,
            Data_Status TEXT,
            Gestao_Data_Status TEXT,
            Negocio_Contrato TEXT,
            Contrato_Codigo TEXT,
            Gestao_GN TEXT,
            "Valores de Proposta_Vr_Interm" TEXT
        )
    '''
}

INDICES_PADRAO = [
    'CREATE INDEX IF NOT EXISTS idx_hist_colab ON Databricks_Historico (Colaborador_Visita)',
    'CREATE INDEX IF NOT EXISTS idx_hist_data ON Databricks_Historico (Data_Agendamento)',
    'CREATE INDEX IF NOT EXISTS idx_pag_colab ON dt_ctrl_pagamento_visita (Colaborador)',
    'CREATE INDEX IF NOT EXISTS idx_gn_colab ON dt_gestao_negocios_finalizados (Atendimento_Colaborador_Visita)'
]


def obter_chave_criptografia() -> bytes:
    """Obtém a chave DB_ENCRYPTION_KEY do ambiente (.env ou Vercel)."""
    chave = os.getenv('DB_ENCRYPTION_KEY', '').strip()
    if not chave:
        raise ValueError(
            "ERRO: A variável 'DB_ENCRYPTION_KEY' não foi encontrada no .env ou nas variáveis da Vercel!"
        )
    return chave.encode('utf-8')


def gerar_nova_chave() -> str:
    """Gera uma nova chave Fernet (AES-128-CBC + HMAC-SHA256) segura."""
    return Fernet.generate_key().decode('utf-8')


def inicializar_estrutura_sql(conn: sqlite3.Connection):
    """Garante que todas as tabelas e índices padrão existam no banco SQLite."""
    cursor = conn.cursor()
    for nome_tabela, ddl in TABELAS_PADRAO.items():
        cursor.execute(ddl)
    for idx_sql in INDICES_PADRAO:
        try:
            cursor.execute(idx_sql)
        except Exception:
            pass
    conn.commit()


def criptografar_banco_local(db_path: str = LOCAL_DB_PATH, enc_path: str = ENCRYPTED_DB_PATH) -> str:
    """
    Compacta (zlib) e criptografa (Fernet AES) o arquivo SQLite local,
    gerando o arquivo seguro .enc que pode ser enviado para a Vercel/GitHub sem risco de vazamento.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Banco de dados local não encontrado em: {db_path}")

    chave = obter_chave_criptografia()
    fernet = Fernet(chave)

    with open(db_path, 'rb') as f:
        dados_brutos = f.read()

    # Compacta antes de criptografar para reduzir drasticamente o tamanho no Git/Vercel
    dados_compactados = zlib.compress(dados_brutos, level=9)
    dados_criptografados = fernet.encrypt(dados_compactados)

    os.makedirs(os.path.dirname(enc_path), exist_ok=True)
    with open(enc_path, 'wb') as f:
        f.write(dados_criptografados)

    return enc_path


def descriptografar_banco_para_tmp(enc_path: str = ENCRYPTED_DB_PATH, tmp_path: str = TMP_DB_PATH) -> str:
    """
    Descriptografa e descompacta o arquivo .enc para o diretório temporário do servidor (ex: /tmp na Vercel).
    Só refaz a descriptografia se o arquivo .enc for mais recente que o arquivo em /tmp.
    """
    if not os.path.exists(enc_path):
        raise FileNotFoundError(f"Arquivo de banco criptografado não encontrado: {enc_path}")

    # Se já foi descriptografado nesta instância serverless e está atualizado, reutiliza!
    if os.path.exists(tmp_path):
        if os.path.getmtime(tmp_path) >= os.path.getmtime(enc_path) and os.path.getsize(tmp_path) > 0:
            return tmp_path

    chave = obter_chave_criptografia()
    fernet = Fernet(chave)

    with open(enc_path, 'rb') as f:
        dados_criptografados = f.read()

    dados_compactados = fernet.decrypt(dados_criptografados)
    dados_brutos = zlib.decompress(dados_compactados)

    with open(tmp_path, 'wb') as f:
        f.write(dados_brutos)

    return tmp_path


def obter_caminho_banco_ativo() -> str:
    """
    Retorna o caminho do banco SQLite pronto para uso:
    1. Se estiver na máquina local e `data/dados_analiticos.db` existir, usa ele diretamente (permite leitura e escrita).
    2. Se estiver na Vercel (onde `.db` não sobe, apenas `.enc`), descriptografa `data/dados_analiticos.enc` para `/tmp` e usa de lá.
    3. Se nenhum existir ainda localmente, cria o banco local com a estrutura padrão vazia.
    """
    if os.path.exists(LOCAL_DB_PATH):
        return LOCAL_DB_PATH

    if os.path.exists(ENCRYPTED_DB_PATH):
        return descriptografar_banco_para_tmp()

    # Fallback local: cria o banco vazio na pasta data/ para não quebrar a aplicação
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(LOCAL_DB_PATH)
        inicializar_estrutura_sql(conn)
        conn.close()
        return LOCAL_DB_PATH
    except OSError:
        # Caso esteja em ambiente read-only (Vercel) sem o arquivo .enc ainda
        conn = sqlite3.connect(TMP_DB_PATH)
        inicializar_estrutura_sql(conn)
        conn.close()
        return TMP_DB_PATH


def obter_conexao_sql() -> sqlite3.Connection:
    """Abre e retorna uma conexão SQLite configurada com Row factory."""
    caminho_db = obter_caminho_banco_ativo()
    conn = sqlite3.connect(caminho_db)
    conn.row_factory = sqlite3.Row
    return conn


def listar_tabelas_sql() -> list:
    """Retorna a lista de tabelas existentes no banco SQLite."""
    conn = obter_conexao_sql()
    inicializar_estrutura_sql(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tabelas = [row['name'] for row in cursor.fetchall()]
    conn.close()
    return tabelas
