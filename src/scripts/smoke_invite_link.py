import traceback
import uuid

from cadastros.models import Condominio
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

User = get_user_model()
RESULT_FILE = "/tmp/smoke_invite_link_result.txt"


def build_cnpj(seed):
    digits = "99999999" + seed[:6]
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


try:
    suffix = uuid.uuid4().hex[:8]
    cond = Condominio.objects.create(
        nome=f"Condominio Link {suffix}",
        cnpj=build_cnpj(suffix),
        telefone="11999990000",
        cep="01310930",
        numero="10",
        is_ativo=True,
    )

    admin = User.objects.create_user(
        username=f"admin_{suffix}",
        password="Temp@12345",
        full_name="Admin Teste",
        first_name="Admin",
        last_name="Teste",
        email=f"admin_{suffix}@mail.com",
        cpf="93541134780",
        phone="11999990001",
        is_staff=True,
        condominio=cond,
        is_active=True,
    )

    sindico = User.objects.create_user(
        username=f"sind_{suffix}",
        password="Temp@12345",
        full_name="Sindico Teste",
        first_name="Sindico",
        last_name="Teste",
        email=f"sind_{suffix}@mail.com",
        cpf="11144477735",
        phone="11999990002",
        condominio=cond,
        is_active=True,
    )

    group, _ = Group.objects.get_or_create(name="Síndicos")
    sindico.groups.add(group)

    client = APIClient()

    # Staff
    admin_token, _ = Token.objects.get_or_create(user=admin)
    client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")
    r1 = client.get(
        "/api/access/signup/invite-link/",
        {"condominio_id": cond.id, "frontend_base": "http://localhost:5173"},
    )
    assert r1.status_code == 200, r1.content
    assert r1.json().get("signup_url"), r1.json()

    # Sindico do próprio condomínio
    sind_token, _ = Token.objects.get_or_create(user=sindico)
    client.credentials(HTTP_AUTHORIZATION=f"Token {sind_token.key}")
    r2 = client.get(
        "/api/access/signup/invite-link/",
        {"frontend_base": "http://localhost:5173"},
    )
    assert r2.status_code == 200, r2.content
    assert r2.json().get("signup_url"), r2.json()

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        f.write("OK\n")
        f.write(str(r2.json().get("signup_url") or "") + "\n")
except Exception:
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        f.write("ERROR\n")
        f.write(traceback.format_exc())
