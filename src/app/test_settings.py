"""
Settings exclusivos para testes. Usa SQLite em memória para evitar
depender do banco remoto (Supabase) e tornar os testes muito mais rápidos.

Uso:
  python manage.py test --settings=app.test_settings <caminho.do.teste>
"""

from app.settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Desabilita logs durante testes
LOGGING = {}

# Chave usada apenas localmente — sem risco
SECRET_KEY = "test-secret-key-only-for-local-tests"

# E-mail fictício para testes (substituído por mocks no código)
RESEND_API_KEY = "re_test_fake_key"
EMAIL_FROM = "noreply@test.example.com"
