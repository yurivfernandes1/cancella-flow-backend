from urllib.parse import urlparse

from cadastros.models import Condominio, Unidade
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()


def _build_login_url(request):
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


def _enviar_email_novo_usuario_com_acesso(
    request, user, senha_temporaria, perfil_label
):
    import resend

    if not user.email:
        return False

    api_key = django_settings.RESEND_API_KEY
    email_from = django_settings.EMAIL_FROM
    if not api_key:
        return False

    login_url = _build_login_url(request)
    nome = user.full_name or user.username

    html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
    <div style="background:#19294a;padding:20px 24px;text-align:center;">
        <p style="color:#ffffff;margin:0;font-size:1rem;font-weight:600;">Cancella Flow</p>
    </div>
    <div style="padding:24px;background:#ffffff;">
        <h2 style="color:#19294a;margin:0 0 12px;font-size:1.1rem;">Olá, {nome}!</h2>
        <p style="color:#374151;line-height:1.6;margin:0 0 16px;">
            Seu cadastro de <strong>{perfil_label}</strong> foi criado com sucesso.
            Use os dados abaixo para seu primeiro acesso:
        </p>
        <table style="width:100%;border-collapse:collapse;margin:0 0 20px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">
            <tr>
                <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;">Link de acesso</td>
                <td style="padding:8px 12px;color:#111827;font-weight:500;"><a href="{login_url}" style="color:#2563eb;text-decoration:none;">{login_url}</a></td>
            </tr>
            <tr>
                <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;">Usuário</td>
                <td style="padding:8px 12px;color:#111827;font-weight:600;">{user.username}</td>
            </tr>
            <tr>
                <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;">Senha temporária</td>
                <td style="padding:8px 12px;color:#111827;font-weight:600;">{senha_temporaria}</td>
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
        resend.Emails.send(
            {
                "from": email_from,
                "to": [user.email],
                "subject": "Seu acesso ao Cancella Flow foi criado",
                "html": html_body,
            }
        )
        return True
    except Exception:
        return False


class UserCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Verificar permissões baseadas no tipo de usuário que está sendo criado
        user_type = request.data.get("user_type", "funcionario")

        # Perfis administrativos continuam restritos ao admin/staff
        if user_type in [
            "sindico",
            "sindico_morador",
            "cerimonialista",
        ]:
            if not (
                request.user.is_staff
                or request.user.groups.filter(name__iexact="admin").exists()
            ):
                return Response(
                    {
                        "error": "Apenas administradores podem criar este tipo de usuário"
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Cerimonialista também pode criar organizador/recepção
        elif user_type in ["recepcao", "organizador_evento"]:
            if not (
                request.user.is_staff
                or request.user.groups.filter(name__iexact="admin").exists()
                or request.user.groups.filter(name="Cerimonialista").exists()
            ):
                return Response(
                    {"error": "Acesso negado para criar este tipo de usuário"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Síndicos podem criar funcionários e moradores
        elif user_type in ["funcionario", "morador"]:
            if not (
                request.user.is_staff
                or request.user.groups.filter(name__iexact="admin").exists()
                or request.user.groups.filter(name__iexact="Síndicos").exists()
            ):
                return Response(
                    {"error": "Acesso negado para criar este tipo de usuário"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            # Determinar condomínio
            condominio = None
            if user_type in ["sindico", "sindico_morador"]:
                condominio_id = request.data.get("condominio_id")
                if not condominio_id:
                    return Response(
                        {
                            "error": "Condomínio é obrigatório para este tipo de usuário"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                try:
                    condominio = Condominio.objects.get(id=condominio_id)
                except Condominio.DoesNotExist:
                    return Response(
                        {"error": "Condomínio não encontrado"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            elif user_type in ["recepcao", "organizador_evento"]:
                condominio_id = request.data.get("condominio_id") or (
                    request.user.condominio.id
                    if getattr(request.user, "condominio", None)
                    else None
                )
                if condominio_id:
                    try:
                        condominio = Condominio.objects.get(id=condominio_id)
                    except Condominio.DoesNotExist:
                        return Response(
                            {"error": "Condomínio não encontrado"},
                            status=status.HTTP_404_NOT_FOUND,
                        )
            elif user_type == "cerimonialista":
                # Cerimonialista não é vinculado a condomínio.
                condominio = None
            else:
                # Funcionário/Morador: usar da requisição, senão o do usuário logado
                condominio_id = request.data.get("condominio_id") or (
                    request.user.condominio.id
                    if getattr(request.user, "condominio", None)
                    else None
                )
                if condominio_id:
                    try:
                        condominio = Condominio.objects.get(id=condominio_id)
                    except Condominio.DoesNotExist:
                        condominio = None

            unidade = None
            unidade_id = request.data.get("unidade_id")

            # Morador e síndico_morador exigem unidade obrigatória
            if user_type in ["morador", "sindico_morador"] and not unidade_id:
                return Response(
                    {
                        "error": "Unidade é obrigatória para cadastro de morador"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if unidade_id:
                try:
                    unidade = Unidade.objects.get(id=unidade_id)
                except Unidade.DoesNotExist:
                    return Response(
                        {"error": "Unidade não encontrada"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            with transaction.atomic():
                senha_temporaria = request.data.get("password", "").strip()
                user = User.objects.create_user(
                    username=request.data.get("username", "").lower(),
                    password=senha_temporaria,
                    first_name=request.data.get("first_name", "").strip(),
                    last_name=request.data.get("last_name", "").strip(),
                    full_name=request.data.get("full_name", "").strip()
                    or f"{request.data.get('first_name', '').strip()} {request.data.get('last_name', '').strip()}",
                    email=request.data.get("email", "").strip(),
                    cpf=request.data.get("cpf", "").strip(),
                    phone=request.data.get("phone", "").strip(),
                    is_staff=request.data.get("is_staff", False),
                    is_active=True,
                    condominio=condominio,
                    created_by=request.user,
                )

                if unidade:
                    user.unidades.add(unidade)

                # Associar ao grupo correto baseado no tipo
                # Se for 'sindico_morador', adicionar aos dois grupos
                group_names = []
                if user_type == "sindico_morador":
                    try:
                        sindico_group, _ = Group.objects.get_or_create(
                            name="Síndicos"
                        )
                        morador_group, _ = Group.objects.get_or_create(
                            name="Moradores"
                        )
                        user.groups.add(sindico_group, morador_group)
                        group_names = ["Síndicos", "Moradores"]
                    except Exception as e:
                        print(
                            f"Erro ao associar grupos para síndico_morador: {e}"
                        )
                else:
                    group_mapping = {
                        "sindico": "Síndicos",
                        "portaria": "Portaria",
                        "morador": "Moradores",
                        "cerimonialista": "Cerimonialista",
                        "recepcao": "Recepção",
                        "organizador_evento": "Organizador do Evento",
                    }

                    group_name = group_mapping.get(user_type)
                    if group_name:
                        try:
                            group, _ = Group.objects.get_or_create(
                                name=group_name
                            )
                            user.groups.add(group)
                            group_names = [group_name]
                        except Exception as e:
                            print(f"Erro ao associar grupo {group_name}: {e}")

                user.save()

                email_enviado = False
                email_erro = None
                if (
                    user_type
                    in {
                        "cerimonialista",
                        "organizador_evento",
                        "recepcao",
                    }
                    and senha_temporaria
                ):
                    perfil_label_map = {
                        "cerimonialista": "Cerimonialista",
                        "organizador_evento": "Organizador do Evento",
                        "recepcao": "Recepção",
                    }
                    if not user.email:
                        email_erro = "Usuário sem e-mail cadastrado"
                    elif not django_settings.RESEND_API_KEY:
                        email_erro = "RESEND_API_KEY ausente"
                    elif not django_settings.EMAIL_FROM:
                        email_erro = "EMAIL_FROM ausente"
                    else:
                        email_enviado = _enviar_email_novo_usuario_com_acesso(
                            request,
                            user,
                            senha_temporaria,
                            perfil_label_map.get(user_type, "Usuário"),
                        )
                        if not email_enviado:
                            email_erro = "Falha ao enviar e-mail pelo provedor"

                return Response(
                    {
                        "message": f"{user_type.capitalize()} criado com sucesso",
                        "id": user.id,
                        "username": user.username,
                        "user_type": user_type,
                        "groups": group_names,
                        "email_enviado": email_enviado,
                        "email_erro": email_erro,
                        "condominio_id": user.condominio.id
                        if user.condominio
                        else None,
                    },
                    status=status.HTTP_201_CREATED,
                )

        except ValidationError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Erro ao criar usuário: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
