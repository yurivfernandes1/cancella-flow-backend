import re
from html import escape
from urllib.parse import urlparse

from app.utils.validators import format_cpf
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()
USERNAME_REGEX = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])?$")


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "t",
            "sim",
            "s",
            "yes",
            "y",
            "ativo",
        }
    return bool(value)


def _build_login_url(request):
    # Prefer explicit setting `FRONTEND_BASE_URL`, fallback to request headers
    frontend_base = getattr(
        django_settings, "FRONTEND_BASE_URL", ""
    ) or request.headers.get("Origin")

    if not frontend_base:
        referer = request.headers.get("Referer", "")
        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                frontend_base = f"{parsed.scheme}://{parsed.netloc}"

    frontend_base = str(frontend_base or "").rstrip("/")
    if not frontend_base:
        frontend_base = "https://cancellaflow.com.br"

    return f"{frontend_base}/login"


def _enviar_email_aprovacao_morador(request, user, senha_temporaria):
    import base64
    import io

    import resend

    if not user.email:
        return False

    api_key = django_settings.RESEND_API_KEY
    email_from = django_settings.EMAIL_FROM
    if not api_key:
        return False

    condominio = getattr(user, "condominio", None)
    condominio_nome = getattr(condominio, "nome", None) or "Condomínio"
    login_url = _build_login_url(request)
    safe_condominio_nome = escape(str(condominio_nome or ""))

    logo_html = ""
    logo_bytes = None
    try:
        from PIL import Image

        if condominio and getattr(condominio, "logo_db_data", None):
            image_buffer = io.BytesIO(bytes(condominio.logo_db_data))
            img = Image.open(image_buffer).convert("RGBA")
            img.thumbnail((220, 80), Image.LANCZOS)
            out_buffer = io.BytesIO()
            img.save(out_buffer, format="PNG")
            logo_bytes = out_buffer.getvalue()
            logo_html = (
                f'<img src="cid:logo" alt="{safe_condominio_nome}" '
                'style="max-width:220px;max-height:80px;margin-top:8px;" />'
            )
    except Exception:
        logo_html = ""
        logo_bytes = None

    nome = user.full_name or user.username
    safe_nome = escape(str(nome or ""))
    safe_login_url = escape(str(login_url or ""), quote=True)
    safe_username = escape(str(user.username or ""))
    safe_senha_temporaria = escape(str(senha_temporaria or ""))
    html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
  <div style="background:#19294a;padding:20px 24px;text-align:center;">
        <p style="color:#ffffff;margin:0;font-size:1rem;font-weight:600;">{safe_condominio_nome}</p>
    {logo_html}
  </div>
  <div style="padding:24px;background:#ffffff;">
        <h2 style="color:#19294a;margin:0 0 12px;font-size:1.1rem;">Olá, {safe_nome}!</h2>
    <p style="color:#374151;line-height:1.6;margin:0 0 16px;">
      Seu cadastro foi <strong style="color:#15803d;">aprovado</strong>.
      Use os dados abaixo para seu primeiro acesso:
    </p>
    <table style="width:100%;border-collapse:collapse;margin:0 0 20px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">
      <tr>
        <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;">Link de acesso</td>
                <td style="padding:8px 12px;color:#111827;font-weight:500;"><a href="{safe_login_url}" style="color:#2563eb;text-decoration:none;">{safe_login_url}</a></td>
      </tr>
      <tr>
        <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;">Usuário</td>
                <td style="padding:8px 12px;color:#111827;font-weight:600;">{safe_username}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;">Senha temporária</td>
                <td style="padding:8px 12px;color:#111827;font-weight:600;">{safe_senha_temporaria}</td>
      </tr>
    </table>
    <p style="color:#92400e;font-size:0.86rem;margin:0;">
      Por segurança, altere sua senha no primeiro login.
    </p>
  </div>
</div>
"""

    try:
        resend.api_key = api_key
        payload = {
            "from": email_from,
            "to": [user.email],
            "subject": "Seu acesso ao Cancella Flow foi aprovado",
            "html": html_body,
        }
        if logo_bytes:
            payload["attachments"] = [
                {
                    "filename": "logo.png",
                    "content": base64.b64encode(logo_bytes).decode(),
                    "content_id": "logo",
                    "disposition": "inline",
                }
            ]
        resend.Emails.send(payload)
        return True
    except Exception:
        return False


def _enviar_email_reset_senha(request, user, nova_senha):
    import base64
    import io

    import resend

    if not user.email:
        return False

    api_key = django_settings.RESEND_API_KEY
    email_from = django_settings.EMAIL_FROM
    if not api_key:
        return False

    condominio = getattr(user, "condominio", None)
    condominio_nome = getattr(condominio, "nome", None) or "Condomínio"
    login_url = _build_login_url(request)
    safe_condominio_nome = escape(str(condominio_nome or ""))

    logo_html = ""
    logo_bytes = None
    try:
        from PIL import Image

        if condominio and getattr(condominio, "logo_db_data", None):
            image_buffer = io.BytesIO(bytes(condominio.logo_db_data))
            img = Image.open(image_buffer).convert("RGBA")
            img.thumbnail((220, 80), Image.LANCZOS)
            out_buffer = io.BytesIO()
            img.save(out_buffer, format="PNG")
            logo_bytes = out_buffer.getvalue()
            logo_html = (
                f'<img src="cid:logo" alt="{safe_condominio_nome}" '
                'style="max-width:220px;max-height:80px;margin-top:8px;" />'
            )
    except Exception:
        logo_html = ""
        logo_bytes = None

    nome = user.full_name or user.username
    safe_nome = escape(str(nome or ""))
    safe_login_url = escape(str(login_url or ""), quote=True)
    safe_username = escape(str(user.username or ""))
    safe_nova_senha = escape(str(nova_senha or ""))
    html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
    <div style="background:#19294a;padding:20px 24px;text-align:center;">
        <p style="color:#ffffff;margin:0;font-size:1rem;font-weight:600;">{safe_condominio_nome}</p>
        {logo_html}
    </div>
    <div style="padding:24px;background:#ffffff;">
        <h2 style="color:#19294a;margin:0 0 12px;font-size:1.1rem;">Olá, {safe_nome}!</h2>
        <p style="color:#374151;line-height:1.6;margin:0 0 16px;">
            Sua senha foi alterada por um administrador. Use os dados abaixo para acessar:
        </p>
        <table style="width:100%;border-collapse:collapse;margin:0 0 20px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">
            <tr>
                <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;">Link de acesso</td>
                <td style="padding:8px 12px;color:#111827;font-weight:500;"><a href="{safe_login_url}" style="color:#2563eb;text-decoration:none;">{safe_login_url}</a></td>
            </tr>
            <tr>
                <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;">Usuário</td>
                <td style="padding:8px 12px;color:#111827;font-weight:600;">{safe_username}</td>
            </tr>
            <tr>
                <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;">Senha</td>
                <td style="padding:8px 12px;color:#111827;font-weight:600;">{safe_nova_senha}</td>
            </tr>
        </table>
        <p style="color:#92400e;font-size:0.86rem;margin:0;">
            Por segurança, altere sua senha após o primeiro acesso.
        </p>
    </div>
</div>
"""

    try:
        resend.api_key = api_key
        payload = {
            "from": email_from,
            "to": [user.email],
            "subject": "Sua senha no Cancella Flow foi alterada",
            "html": html_body,
        }
        if logo_bytes:
            payload["attachments"] = [
                {
                    "filename": "logo.png",
                    "content": base64.b64encode(logo_bytes).decode(),
                    "content_id": "logo",
                    "disposition": "inline",
                }
            ]
        resend.Emails.send(payload)
        return True
    except Exception:
        return False


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Buscar os grupos do usuário
        groups = user.groups.all().values("id", "name")

        return Response(
            {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.full_name,
                "email": user.email,
                "cpf": user.cpf,
                "phone": user.phone,
                "first_access": user.first_access,
                "is_staff": user.is_staff,
                "is_active": user.is_active,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "groups": list(groups),
                "condominio_id": user.condominio.id
                if user.condominio
                else None,
                "condominio_nome": user.condominio.nome
                if user.condominio
                else None,
                "foto_url": f"/access/profile/{user.id}/foto-db/"
                if user.foto_db_data
                else None,
                "unidade_id": user.unidades.values_list(
                    "id", flat=True
                ).first(),
                "unidade_identificacao": user.unidades.first().identificacao_completa
                if user.unidades.exists()
                else None,
                "unidades": [
                    {
                        "id": str(u.id),
                        "identificacao_completa": u.identificacao_completa,
                    }
                    for u in user.unidades.all()
                ],
            }
        )

    def patch(self, request, user_id=None):
        try:
            # Determinar usuário alvo da atualização
            target_user = None
            is_sindico_requester = request.user.groups.filter(
                name="Síndicos"
            ).exists()
            was_inactive = False
            activated_now = False
            should_delete_pending_user = False

            if user_id is None:
                target_user = request.user
            else:
                # Se o id for do próprio usuário, sempre permitir
                if request.user.id == user_id:
                    target_user = request.user
                else:
                    # Staff pode editar qualquer usuário
                    if request.user.is_staff:
                        target_user = User.objects.get(id=user_id)
                    # Síndicos podem editar usuários do mesmo condomínio
                    elif request.user.groups.filter(name="Síndicos").exists():
                        candidate = User.objects.get(id=user_id)
                        if getattr(
                            request.user, "condominio_id", None
                        ) and request.user.condominio_id == getattr(
                            candidate, "condominio_id", None
                        ):
                            target_user = candidate
                        else:
                            return Response(
                                {
                                    "error": "Você não tem permissão para editar este usuário."
                                },
                                status=status.HTTP_403_FORBIDDEN,
                            )
                    elif request.user.groups.filter(
                        name="Cerimonialista"
                    ).exists():
                        candidate = User.objects.get(id=user_id)
                        pode_editar_grupo = candidate.groups.filter(
                            name__in=["Organizador do Evento", "Recepção"]
                        ).exists()
                        if (
                            pode_editar_grupo
                            and candidate.created_by_id == request.user.id
                        ):
                            target_user = candidate
                        else:
                            return Response(
                                {
                                    "error": "Você não tem permissão para editar este usuário."
                                },
                                status=status.HTTP_403_FORBIDDEN,
                            )
                    else:
                        return Response(
                            {
                                "error": "Você não tem permissão para editar este usuário."
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )

            # Campo especial para senha
            senha_alterada_por_terceiro = False
            nova_senha_fornecida = None
            senha_email_enviado = False
            senha_email_erro = None
            if "password" in request.data:
                nova_senha_fornecida = request.data["password"]
                target_user.set_password(nova_senha_fornecida)
                # Se quem está fazendo a alteração não for o próprio usuário, marcar para envio de e-mail
                if request.user.id != target_user.id:
                    senha_alterada_por_terceiro = True
                    # Forçar alteração de senha no próximo login
                    target_user.first_access = True

            was_inactive = not bool(target_user.is_active)

            # Atualiza outros campos
            allowed_fields = [
                "full_name",
                "first_name",
                "last_name",
                "username",
                "email",
                "cpf",
                "phone",
                "is_active",
                # "is_staff" somente para admin (verificado abaixo)
            ]

            for field in allowed_fields:
                if field in request.data:
                    if field == "is_active":
                        new_is_active = _to_bool(request.data[field])
                        if was_inactive and new_is_active:
                            activated_now = True
                        target_user.is_active = new_is_active
                    else:
                        setattr(target_user, field, request.data[field])

            if "username" in request.data:
                username = (
                    str(request.data.get("username") or "").strip().lower()
                )
                if not USERNAME_REGEX.match(username):
                    return Response(
                        {
                            "error": "Nome de usuário inválido. Use 3 a 30 caracteres com letras minúsculas, números, ponto, hífen ou underline."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if (
                    User.objects.filter(username=username)
                    .exclude(id=target_user.id)
                    .exists()
                ):
                    return Response(
                        {"error": "Nome de usuário já está em uso."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                target_user.username = username

            # is_staff só pode ser alterado por staff
            if "is_staff" in request.data and request.user.is_staff:
                target_user.is_staff = bool(request.data["is_staff"])

            # Atualizar condomínio se fornecido
            if "condominio_id" in request.data:
                if request.data["condominio_id"]:
                    from cadastros.models import Condominio

                    try:
                        condominio = Condominio.objects.get(
                            id=request.data["condominio_id"]
                        )
                        target_user.condominio = condominio
                    except Condominio.DoesNotExist:
                        return Response(
                            {"error": "Condomínio não encontrado"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    target_user.condominio = None

            # Adicionar unidade (add_unidade_id ou unidade_id como alias retrocompatível)
            # Nota: unidade_id:null não é mais suportado — use remove_unidade_id
            add_id = request.data.get("add_unidade_id") or (
                request.data.get("unidade_id")
                if request.data.get("unidade_id")
                else None
            )
            if add_id:
                from cadastros.models import Unidade

                try:
                    unidade = Unidade.objects.get(id=add_id)
                    target_user.unidades.add(unidade)
                except Unidade.DoesNotExist:
                    return Response(
                        {"error": "Unidade não encontrada"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Remover unidade específica
            if (
                "remove_unidade_id" in request.data
                and request.data["remove_unidade_id"]
            ):
                from cadastros.models import Unidade

                try:
                    unidade = Unidade.objects.get(
                        id=request.data["remove_unidade_id"]
                    )
                    target_user.unidades.remove(unidade)
                except Unidade.DoesNotExist:
                    pass  # silencioso — pode ter sido removida antes

                # Rejeição de pendente: inativo e ação de desvincular por síndico/admin => excluir usuário
                if not target_user.is_active and (
                    request.user.is_staff or is_sindico_requester
                ):
                    should_delete_pending_user = True

                # Se não sobrou nenhuma unidade, remover automaticamente do grupo Moradores
                if not target_user.unidades.exists():
                    try:
                        grupo_moradores = Group.objects.get(name="Moradores")
                        target_user.groups.remove(grupo_moradores)
                    except Group.DoesNotExist:
                        pass

                    # Mantém o usuário sem o grupo caso não haja unidades.

            # Gerenciar grupo Moradores via campo is_morador
            if "is_morador" in request.data:
                try:
                    grupo_moradores = Group.objects.get(name="Moradores")
                    is_morador = _to_bool(request.data["is_morador"])

                    if is_morador:
                        # Adicionar ao grupo Moradores se não estiver
                        if not target_user.groups.filter(
                            id=grupo_moradores.id
                        ).exists():
                            target_user.groups.add(grupo_moradores)
                    else:
                        # Remover do grupo Moradores se estiver
                        if target_user.groups.filter(
                            id=grupo_moradores.id
                        ).exists():
                            target_user.groups.remove(grupo_moradores)
                except Group.DoesNotExist:
                    return Response(
                        {"error": "Grupo Moradores não encontrado"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Validar/normalizar CPF e evitar colisão com o próprio registro
            if "cpf" in request.data and request.data["cpf"]:
                try:
                    cpf_normalizado = format_cpf(str(request.data["cpf"]))
                except Exception:
                    cpf_normalizado = str(request.data["cpf"])  # fallback

                if (
                    User.objects.filter(cpf=cpf_normalizado)
                    .exclude(id=target_user.id)
                    .exists()
                ):
                    return Response(
                        {"error": "CPF já cadastrado para outro usuário."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # aplica o cpf normalizado antes de salvar
                target_user.cpf = cpf_normalizado

            if should_delete_pending_user:
                target_user.delete()
                return Response(
                    {
                        "message": "Cadastro pendente rejeitado. Usuário removido com sucesso."
                    }
                )

            senha_temporaria_aprovacao = None
            email_enviado = False
            if activated_now:
                senha_temporaria_aprovacao = (
                    User.objects.make_random_password()
                )
                target_user.set_password(senha_temporaria_aprovacao)
                target_user.first_access = True

            target_user.save()

            if activated_now:
                email_enviado = _enviar_email_aprovacao_morador(
                    request,
                    target_user,
                    senha_temporaria_aprovacao,
                )

            # Enviar e-mail informando usuário e nova senha quando alterado por administrador/síndico
            if senha_alterada_por_terceiro and nova_senha_fornecida:
                if not target_user.email:
                    senha_email_erro = "Usuário sem e-mail cadastrado"
                elif not django_settings.RESEND_API_KEY:
                    senha_email_erro = "RESEND_API_KEY ausente"
                elif not django_settings.EMAIL_FROM:
                    senha_email_erro = "EMAIL_FROM ausente"
                else:
                    try:
                        senha_email_enviado = _enviar_email_reset_senha(
                            request, target_user, nova_senha_fornecida
                        )
                    except Exception:
                        senha_email_enviado = False
                    if not senha_email_enviado:
                        senha_email_erro = (
                            "Falha ao enviar e-mail pelo provedor"
                        )

            return Response(
                {
                    "message": "Atualizado com sucesso",
                    "email_enviado": email_enviado,
                    "aprovacao_realizada": activated_now,
                    "senha_email_enviado": senha_email_enviado,
                    "senha_email_erro": senha_email_erro,
                }
            )

        except User.DoesNotExist:
            return Response(
                {"error": "Usuário não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
