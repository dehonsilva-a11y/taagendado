import os
import sys
import sqlite3
import pandas as pd

# Adiciona a pasta raiz do projeto ao sys.path para importar o pacote `app`
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
from app.database import (
    LOCAL_DB_PATH,
    ENCRYPTED_DB_PATH,
    DATA_DIR,
    inicializar_estrutura_sql,
    criptografar_banco_local,
    gerar_nova_chave
)

PLANILHAS_DIR = os.path.join(DATA_DIR, 'planilhas')
ENV_PATH = os.path.join(BASE_DIR, '.env')

# Mapeamento automático das planilhas em data/planilhas/ para as tabelas SQL
# Se você colocar qualquer um desses arquivos na pasta data/planilhas/, ele será importado!
MAPA_PLANILHAS = {
    'Databricks_Historico.xlsx': {
        'tabela': 'Databricks_Historico',
        'coluna_id': 'Id_Visita'
    },
    'dt_ctrl_pagamento_visita.xlsx': {
        'tabela': 'dt_ctrl_pagamento_visita',
        'coluna_id': None
    },
    'dt_gestao_negocios_finalizados.xlsx': {
        'tabela': 'dt_gestao_negocios_finalizados',
        'coluna_id': None
    }
}


def garantir_chave_no_env():
    """Verifica se DB_ENCRYPTION_KEY existe no .env; se não existir, gera e salva automaticamente."""
    load_dotenv(ENV_PATH)
    chave = os.getenv('DB_ENCRYPTION_KEY', '').strip()
    if not chave:
        nova_chave = gerar_nova_chave()
        with open(ENV_PATH, 'a', encoding='utf-8') as f:
            f.write(f"\n# Chave de Criptografia do Banco SQLite para a Vercel\nDB_ENCRYPTION_KEY={nova_chave}\n")
        os.environ['DB_ENCRYPTION_KEY'] = nova_chave
        print("🔐 Nova chave DB_ENCRYPTION_KEY gerada e adicionada ao seu arquivo .env!")
        print(f"👉 IMPORTANTE: Adicione esta variável na Vercel (Settings -> Environment Variables):")
        print(f"   Nome: DB_ENCRYPTION_KEY")
        print(f"   Valor: {nova_chave}\n")


def importar_planilha_para_sql(conn: sqlite3.Connection, caminho_arquivo: str, nome_tabela: str, modo: str = 'replace', coluna_id: str = None):
    """
    Importa uma planilha Excel ou CSV para a tabela SQLite especificada.
    - modo='replace': substitui a tabela inteira pela planilha atual.
    - modo='append': adiciona apenas novas linhas (filtrando por coluna_id se informada).
    """
    print(f"📂 Lendo arquivo: {os.path.basename(caminho_arquivo)}...")
    if caminho_arquivo.lower().endswith('.csv'):
        df = pd.read_csv(caminho_arquivo, dtype=str).fillna('')
    else:
        df = pd.read_excel(caminho_arquivo, dtype=str).fillna('')

    total_lido = len(df)

    if modo == 'append' and coluna_id and coluna_id in df.columns:
        try:
            existentes_df = pd.read_sql_query(f'SELECT "{coluna_id}" FROM "{nome_tabela}"', conn)
            ids_existentes = set(existentes_df[coluna_id].astype(str).str.strip())
            df[coluna_id] = df[coluna_id].astype(str).str.strip()
            df = df[~df[coluna_id].isin(ids_existentes)]
        except Exception:
            pass

    df.to_sql(nome_tabela, conn, if_exists=modo, index=False)
    print(f"✅ Tabela '{nome_tabela}' atualizada! ({len(df)} registros gravados de {total_lido} lidos)")


def atualizar_banco_noturno(modo: str = 'replace'):
    """
    Rotina principal de atualização noturna:
    1. Garante que a chave de criptografia exista no .env
    2. Cria/atualiza o banco SQLite local em data/dados_analiticos.db
    3. Lê todas as planilhas da pasta data/planilhas/
    4. Cria os índices de performance
    5. Compacta e criptografa o banco gerando data/dados_analiticos.enc pronto para a Vercel!
    """
    print("=" * 60)
    print("🚀 INICIANDO ATUALIZAÇÃO DO BANCO SQL + CRIPTOGRAFIA")
    print("=" * 60)

    garantir_chave_no_env()
    os.makedirs(PLANILHAS_DIR, exist_ok=True)

    conn = sqlite3.connect(LOCAL_DB_PATH)
    inicializar_estrutura_sql(conn)

    arquivos_encontrados = 0
    # 1. Processa planilhas mapeadas
    for nome_arquivo, config in MAPA_PLANILHAS.items():
        caminho = os.path.join(PLANILHAS_DIR, nome_arquivo)
        if os.path.exists(caminho):
            arquivos_encontrados += 1
            importar_planilha_para_sql(
                conn,
                caminho_arquivo=caminho,
                nome_tabela=config['tabela'],
                modo=modo,
                coluna_id=config['coluna_id']
            )

    # 2. Processa qualquer outra planilha (.xlsx ou .csv) que você colocar em data/planilhas/
    # usando o nome do arquivo como nome da tabela!
    for item in os.listdir(PLANILHAS_DIR):
        if item in MAPA_PLANILHAS or item.startswith('~$'):
            continue
        if item.lower().endswith(('.xlsx', '.xls', '.csv')):
            arquivos_encontrados += 1
            nome_tabela = os.path.splitext(item)[0]
            caminho = os.path.join(PLANILHAS_DIR, item)
            importar_planilha_para_sql(conn, caminho, nome_tabela, modo=modo)

    # 3. Recria índices padrão para manter buscas instantâneas
    inicializar_estrutura_sql(conn)
    conn.close()

    if arquivos_encontrados == 0:
        print(f"⚠️ Nenhuma planilha encontrada em: {PLANILHAS_DIR}")
        print("   O banco foi inicializado com as tabelas padrão vazias.")

    # 4. Compacta e criptografa o banco para a Vercel
    print("\n🔒 Compactando e criptografando o banco de dados...")
    enc_path = criptografar_banco_local(LOCAL_DB_PATH, ENCRYPTED_DB_PATH)

    tam_db = os.path.getsize(LOCAL_DB_PATH) / 1024
    tam_enc = os.path.getsize(enc_path) / 1024

    print(f"✅ Arquivo seguro gerado: {enc_path}")
    print(f"📊 Tamanho original (.db): {tam_db:.1f} KB -> Criptografado/Compactado (.enc): {tam_enc:.1f} KB")
    print("=" * 60)
    print("🎉 Tudo pronto! O arquivo 'data/dados_analiticos.enc' já está seguro para subir para a Vercel.")


if __name__ == '__main__':
    # Permite passar --append no terminal se quiser apenas adicionar registros sem limpar a tabela
    modo_execucao = 'append' if '--append' in sys.argv else 'replace'
    atualizar_banco_noturno(modo=modo_execucao)
