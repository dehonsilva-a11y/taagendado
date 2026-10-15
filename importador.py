import pandas as pd
import sqlite3

def criar_banco():
    print("Criando o banco de dados...")
    conexao = sqlite3.connect('banco.db')
    cursor = conexao.cursor()

    # 1. Tabela de Usuários para o Login
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            filial TEXT,
            email TEXT UNIQUE,
            senha TEXT
        )
    ''')
    # Cria o seu usuário padrão (Senha: 123456)
    cursor.execute('INSERT OR IGNORE INTO usuarios (nome, filial, email, senha) VALUES (?, ?, ?, ?)', 
                   ('Robertty Almeida', '(10) Centro Adm.', 'robertty@lello.com', '123456'))

    # 2. Tabela de Imóveis (Lendo do Excel)
    try:
        df = pd.read_excel('base.xlsx')
        df.to_sql('imoveis', con=conexao, if_exists='replace', index=False)
        print("Tabela de imóveis importada com sucesso!")
    except Exception as e:
        print(f"Aviso: Não foi possível importar base.xlsx ({e})")

    conexao.commit()
    conexao.close()
    print("✅ Banco configurado com sucesso!")

if __name__ == '__main__':
    criar_banco()