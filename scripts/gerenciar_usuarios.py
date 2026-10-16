import firebase_admin
from firebase_admin import credentials, firestore

# Conecta ao Firebase
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def criar_usuario():
    # Digite o e-mail Google exato que a pessoa vai usar para entrar
    email = input("Digite o E-mail Google do usuário: ").strip().lower()
    nome = input("Digite o Nome Completo: ").strip()
    filial = input("Digite a Filial (Ex: (10) Centro Adm.): ").strip()
    
    print("\nGrupos de Acesso Disponíveis:")
    print("1 - Admin\n2 - Gerente Geral\n3 - Gerente Filial\n4 - Agente de Visita\n5 - Corretor")
    opcao = input("Escolha o perfil (1 a 5): ").strip()
    
    perfis = {"1": "Admin", "2": "Gerente Geral", "3": "Gerente Filial", "4": "Agente de Visita", "5": "Corretor"}
    perfil_escolhido = perfis.get(opcao, "Corretor")

    # Cria o registro no Firestore
    dados_usuario = {
        "nome": nome,
        "email": email,
        "filial": filial,
        "perfil": perfil_escolhido,
        "ativo": True # Se quiser demitir/bloquear alguém, mude isso para False no Firebase
    }
    
    # Salva usando o e-mail como ID do documento
    db.collection("usuarios").document(email).set(dados_usuario)
    
    print(f"\n✅ Usuário {nome} ({perfil_escolhido}) criado com sucesso!")
    print(f"Ele já pode acessar o sistema usando o e-mail {email}.")

if __name__ == '__main__':
    criar_usuario()