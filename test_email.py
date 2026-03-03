import os
import sys

sys.path.insert(0, "src")
from dotenv import load_dotenv

load_dotenv("src/.env")

import resend

api_key = os.getenv("RESEND_API_KEY", "")
email_from = os.getenv("EMAIL_FROM", "")
print(f"key: {api_key[:12] if api_key else 'VAZIA'}")
print(f"from: {email_from}")

resend.api_key = api_key
try:
    r = resend.Emails.send(
        {
            "from": email_from,
            "to": ["yuri.viana.fernandes@gmail.com"],
            "subject": "Teste Cancella Flow",
            "html": "<p>Teste de email</p>",
        }
    )
    print(f"OK: {r}")
except Exception as e:
    print(f"ERRO: {type(e).__name__}: {e}")
