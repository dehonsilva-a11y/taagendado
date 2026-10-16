import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def enviar_email_boas_vindas(email_destino, nome_usuario, perfil_usuario):
    # Puxa estritamente das variáveis de ambiente (sem fallback hardcoded)
    EMAIL_REMETENTE = os.getenv('EMAIL_SISTEMA')
    SENHA_APP = os.getenv('SENHA_EMAIL_SISTEMA') 

    # Se a variável não existir, cancela o envio silenciosamente
    if not EMAIL_REMETENTE or not SENHA_APP:
        print("Aviso: Credenciais de e-mail não configuradas no .env. E-mail ignorado.")
        return

    assunto = "Bem-vindo ao sistema Tá Agendado!"
    corpo_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #0d6efd;">Olá, {nome_usuario}!</h2>
        <p>Seu acesso ao sistema <b>Tá Agendado</b> acabou de ser liberado.</p>
        <p><b>Seu Perfil de Acesso:</b> {perfil_usuario}</p>
        <p>Você já pode acessar a plataforma utilizando o seu e-mail corporativo (Google).</p>
        <br>
        <a href="https://seu-link-da-vercel.vercel.app" style="background-color: #0d6efd; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">Acessar Sistema</a>
      </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = f"Tá Agendado <{EMAIL_REMETENTE}>"
    msg['To'] = email_destino
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo_html, 'html'))

    try:
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(EMAIL_REMETENTE, SENHA_APP)
        servidor.send_message(msg)
        servidor.quit()
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")