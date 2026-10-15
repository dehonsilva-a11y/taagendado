import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import firebase_admin
from firebase_admin import credentials, firestore

# 1. Configuração do Firebase (Híbrida: Vercel vs Local)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(BASE_DIR, 'firebase_key.json')

if not firebase_admin._apps:
    if os.getenv("FIREBASE_CREDENTIALS"):
        cred_dict = json.loads(os.getenv("FIREBASE_CREDENTIALS"))
        cred = credentials.Certificate(cred_dict)
    elif os.path.exists(KEY_PATH):
        cred = credentials.Certificate(KEY_PATH)
    else:
        raise FileNotFoundError("Credenciais do Firebase não encontradas.")
    
    firebase_admin.initialize_app(cred)

db = firestore.client()
colecao_imoveis = db.collection('db_visita_locacao')

# 2. Handler HTTP (compatível com a Vercel)
class handler(BaseHTTPRequestHandler):

    def _responder(self, status_code, dados):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(dados, ensure_ascii=False, default=str).encode('utf-8'))

    def do_OPTIONS(self):
        # Suporte a requisições CORS prévias do navegador
        self._responder(200, {"status": "ok"})

    def do_GET(self):
        """Lista os imóveis cadastrados no Firestore"""
        try:
            docs = colecao_imoveis.stream()
            imoveis = []
            for doc in docs:
                item = doc.to_dict()
                item['id'] = doc.id
                imoveis.append(item)
            
            self._responder(200, {
                "status": "sucesso",
                "total": len(imoveis),
                "dados": imoveis
            })
        except Exception as e:
            self._responder(500, {"status": "erro", "mensagem": str(e)})

    def do_POST(self):
        """Cadastra um novo imóvel direto no Firestore"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            corpo = self.rfile.read(content_length)
            dados_recebidos = json.loads(corpo.decode('utf-8'))

            # Se enviar uma lista de imóveis ou um único imóvel
            if isinstance(dados_recebidos, list):
                batch = db.batch()
                for item in dados_recebidos:
                    doc_ref = colecao_imoveis.document()
                    batch.set(doc_ref, item)
                batch.commit()
                mensagem = f"{len(dados_recebidos)} imóveis cadastrados com sucesso."
            else:
                _, doc_ref = colecao_imoveis.add(dados_recebidos)
                mensagem = f"Imóvel cadastrado com ID: {doc_ref.id}"

            self._responder(201, {"status": "sucesso", "mensagem": mensagem})
        except Exception as e:
            self._responder(400, {"status": "erro", "mensagem": str(e)})

# 3. Rodar localmente via terminal: python api/index.py
if __name__ == '__main__':
    porta = 3000
    servidor = HTTPServer(('localhost', porta), handler)
    print(f"🚀 Servidor local rodando em http://localhost:{porta}")
    print("Rotas disponíveis:")
    print(" - GET  / (retorna todos os imóveis do Firestore)")
    print(" - POST / (envia um JSON para cadastrar imóvel)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")