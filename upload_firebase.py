import sqlite3
import firebase_admin
from firebase_admin import credentials, firestore

# 1. Conectar ao Firebase
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def subir_imoveis():
    print("Lendo dados do SQLite (banco.db)...")
    conexao = sqlite3.connect('banco.db')
    conexao.row_factory = sqlite3.Row
    cursor = conexao.cursor()
    
    # Pega todos os imóveis do banco local
    imoveis = cursor.execute('SELECT * FROM imoveis').fetchall()
    conexao.close()
    
    print(f"Encontrados {len(imoveis)} imóveis. Iniciando upload para o Firestore...")
    
    # Referência para a coleção "imoveis" no Firebase
    colecao_imoveis = db.collection('db_visita_locacao')
    
    contador = 0
    for row in imoveis:
        imovel_dict = dict(row)
        
        # O método .add() faz o Firebase gerar um ID alfanumérico único automaticamente
        colecao_imoveis.add(imovel_dict)
        
        contador += 1
        
        # Mostra o progresso a cada 100 itens para não travar o terminal
        if contador % 100 == 0:
            print(f"Progresso: {contador}/{len(imoveis)} imóveis enviados...")

    print(f"✅ Upload de {contador} imóveis finalizado com sucesso! Verifique o painel do Firebase.")

if __name__ == '__main__':
    subir_imoveis()