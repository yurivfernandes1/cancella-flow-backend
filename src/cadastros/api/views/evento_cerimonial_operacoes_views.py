import base64
import re
import unicodedata
from io import BytesIO
from urllib.parse import urlparse

import qrcode
from access.models import User
from app.utils.validators import validate_cpf
from django.conf import settings as django_settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ...models import (
    EventoCerimonial,
    EventoCerimonialConvite,
    EventoCerimonialFuncionario,
    FuncaoFesta,
)
from ..serializers.evento_cerimonial_aux_serializer import (
    EventoCerimonialConviteSerializer,
    EventoCerimonialFuncionarioSerializer,
    FuncaoFestaSerializer,
)
from .evento_cerimonial_views import (
    _is_participante_evento,
    _pode_editar_evento,
)

_RESTRICTED_GROUPS = {
    "admin",
    "síndicos",
    "sindicos",
    "moradores",
    "portaria",
    "cerimonialista",
    "organizador do evento",
}


def _frontend_base(request):
    base = (
        getattr(django_settings, "FRONTEND_BASE_URL", "")
        or request.headers.get("Origin")
        or "https://cancellaflow.com.br"
    )
    return str(base).rstrip("/")


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


def _signup_url(request, token):
    return f"{_frontend_base(request)}/signup/evento/{token}"


def _qr_data_url(value):
    img = qrcode.make(str(value))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def _enriquecer_convite(request, convite):
    data = EventoCerimonialConviteSerializer(convite).data
    signup_url = _signup_url(request, convite.token)
    data["signup_url"] = signup_url
    data["qr_code_data_url"] = _qr_data_url(signup_url)
    return data


def _normalize_username(value):
    return str(value or "").strip().lower()


def _normalize_cpf(value):
    return "".join(c for c in str(value or "") if c.isdigit())


def _normalize_phone(value):
    return "".join(c for c in str(value or "") if c.isdigit())


def _to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    return str(value).strip().lower() in {
        "1",
        "true",
        "t",
        "sim",
        "s",
        "yes",
        "y",
        "on",
        "ativo",
    }


def _normalize_email(value):
    return str(value or "").strip().lower()


def _sanitize_username_base(value):
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", ".", text)
    text = re.sub(r"\.+", ".", text).strip(".")
    return text


def _build_employee_username(nome, documento):
    base = _sanitize_username_base(nome)
    if not base:
        base = "funcionario"

    suffix = "".join(ch for ch in str(documento or "") if ch.isdigit())[-4:]
    if suffix:
        base = f"{base}.{suffix}"

    candidate = base[:30]
    index = 1
    while User.objects.filter(username=candidate).exists():
        append = f".{index}"
        candidate = f"{base[: max(1, 30 - len(append))]}{append}"
        index += 1

    return candidate


def _pode_gerenciar_usuario_funcionario(request_user, usuario):
    if request_user.is_staff:
        return True
    return usuario.created_by_id == request_user.id


def _usuario_grupos_normalizados(usuario):
    return {
        str(g).strip().lower()
        for g in usuario.groups.values_list("name", flat=True)
    }


def _validar_usuario_funcionario(usuario, is_recepcao):
    grupos = _usuario_grupos_normalizados(usuario)

    if grupos & _RESTRICTED_GROUPS:
        return "O usuário selecionado não pode ser usado como funcionário de evento."

    if not is_recepcao and "recepção" in grupos:
        return "Usuário de recepção deve ser vinculado como funcionário de recepção."

    return None


def _enviar_email_acesso_funcionario(request, user, senha_temporaria):
    import resend

    if not user.email:
        return False, "Usuário sem e-mail cadastrado"

    api_key = django_settings.RESEND_API_KEY
    email_from = django_settings.EMAIL_FROM
    if not api_key:
        return False, "RESEND_API_KEY ausente"
    if not email_from:
        return False, "EMAIL_FROM ausente"

    login_url = _build_login_url(request)
    nome = user.full_name or user.username

    html_body = f"""
<div style=\"font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;\">
    <div style=\"background:#19294a;padding:20px 24px;text-align:center;\">
        <p style=\"color:#ffffff;margin:0;font-size:1rem;font-weight:600;\">Cancella Flow</p>
    </div>
    <div style=\"padding:24px;background:#ffffff;\">
        <h2 style=\"color:#19294a;margin:0 0 12px;font-size:1.1rem;\">Olá, {nome}!</h2>
        <p style=\"color:#374151;line-height:1.6;margin:0 0 16px;\">
            Seu acesso de <strong>Recepção</strong> foi atualizado.
            Use os dados abaixo para entrar no sistema:
        </p>
        <table style=\"width:100%;border-collapse:collapse;margin:0 0 20px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;\">
            <tr>
                <td style=\"padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;\">Link de acesso</td>
                <td style=\"padding:8px 12px;color:#111827;font-weight:500;\"><a href=\"{login_url}\" style=\"color:#2563eb;text-decoration:none;\">{login_url}</a></td>
            </tr>
            <tr>
                <td style=\"padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;\">Usuário</td>
                <td style=\"padding:8px 12px;color:#111827;font-weight:600;\">{user.username}</td>
            </tr>
            <tr>
                <td style=\"padding:8px 12px;color:#6b7280;font-size:0.88rem;width:140px;\">Senha temporária</td>
                <td style=\"padding:8px 12px;color:#111827;font-weight:600;\">{senha_temporaria}</td>
            </tr>
        </table>
        <p style=\"color:#92400e;font-size:0.86rem;margin:0;\">
            Por segurança, altere sua senha no primeiro acesso.
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
                "subject": "Seu acesso ao Cancella Flow foi atualizado",
                "html": html_body,
            }
        )
        return True, None
    except Exception:
        return False, "Falha ao enviar e-mail pelo provedor"


def _garantir_grupo_recepcao(usuario):
    group, _ = Group.objects.get_or_create(name="Recepção")
    usuario.groups.add(group)


def _criar_usuario_funcionario(
    request,
    *,
    nome,
    documento,
    email,
    phone,
    is_recepcao,
):
    nome = str(nome or "").strip()
    documento = str(documento or "").strip()
    email = _normalize_email(email)
    phone = str(phone or "").strip()

    if not nome:
        raise ValidationError("Nome do funcionário é obrigatório.")
    if not documento:
        raise ValidationError("Documento do funcionário é obrigatório.")

    documento_digits = _normalize_cpf(documento)
    if (
        documento_digits
        and User.objects.filter(
            Q(cpf=documento_digits) | Q(cpf__endswith=documento_digits)
        ).exists()
    ):
        raise ValidationError(
            "Já existe funcionário com este documento. Selecione na lista de cadastrados."
        )

    if is_recepcao and not email:
        raise ValidationError(
            "E-mail é obrigatório para funcionário de recepção."
        )

    username = _build_employee_username(nome, documento)
    senha_temporaria = User.objects.make_random_password()

    usuario = User.objects.create_user(
        username=username,
        password=senha_temporaria,
        full_name=nome,
        email=email,
        cpf=documento,
        phone=phone,
        is_active=False,
        first_access=True,
        condominio=getattr(request.user, "condominio", None),
        created_by=request.user,
    )

    if is_recepcao:
        _garantir_grupo_recepcao(usuario)

    usuario.save()

    email_enviado = False
    email_erro = None
    ativado = False

    if is_recepcao:
        usuario.is_active = True
        usuario.first_access = True
        usuario.set_password(senha_temporaria)
        usuario.save(update_fields=["is_active", "first_access", "password"])
        ativado = True
        email_enviado, email_erro = _enviar_email_acesso_funcionario(
            request, usuario, senha_temporaria
        )

    return {
        "usuario": usuario,
        "email_enviado": email_enviado,
        "email_erro": email_erro,
        "ativado": ativado,
    }


def _vincular_usuario_existente(
    request,
    *,
    usuario,
    is_recepcao,
    usuario_is_active=None,
):
    if not _pode_gerenciar_usuario_funcionario(request.user, usuario):
        raise ValidationError(
            "Você não pode utilizar este funcionário cadastrado."
        )

    erro_validacao = _validar_usuario_funcionario(usuario, is_recepcao)
    if erro_validacao:
        raise ValidationError(erro_validacao)

    if is_recepcao:
        _garantir_grupo_recepcao(usuario)

    if usuario_is_active is None:
        usuario_is_active = True if is_recepcao else False
    else:
        usuario_is_active = _to_bool(usuario_is_active)

    senha_temporaria = None
    ativado = False

    if usuario_is_active and not usuario.is_active:
        senha_temporaria = User.objects.make_random_password()
        usuario.set_password(senha_temporaria)
        usuario.first_access = True
        ativado = True

    usuario.is_active = bool(usuario_is_active)
    usuario.save()

    email_enviado = False
    email_erro = None
    if senha_temporaria and is_recepcao:
        email_enviado, email_erro = _enviar_email_acesso_funcionario(
            request, usuario, senha_temporaria
        )

    return {
        "usuario": usuario,
        "email_enviado": email_enviado,
        "email_erro": email_erro,
        "ativado": ativado,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_convites_list_view(request, pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related(
            "cerimonialistas"
        ).get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _is_participante_evento(request.user, evento):
        return Response(
            {"error": "Sem permissão para visualizar convites deste evento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    convites = EventoCerimonialConvite.objects.filter(
        evento=evento, ativo=True
    )
    return Response([_enriquecer_convite(request, c) for c in convites])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_convite_generate_view(request, pk, tipo):
    try:
        evento = EventoCerimonial.objects.prefetch_related(
            "cerimonialistas"
        ).get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_editar_evento(request.user, evento):
        return Response(
            {
                "error": "Somente cerimonialistas podem gerar convites do evento."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    tipo = str(tipo or "").strip().lower()
    tipos_validos = {
        EventoCerimonialConvite.TIPO_ORGANIZADOR,
        EventoCerimonialConvite.TIPO_RECEPCAO,
    }
    if tipo not in tipos_validos:
        return Response(
            {"error": "Tipo de convite inválido."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    EventoCerimonialConvite.objects.filter(
        evento=evento,
        tipo=tipo,
        ativo=True,
    ).update(ativo=False)

    convite = EventoCerimonialConvite.objects.create(
        evento=evento,
        tipo=tipo,
        created_by=request.user,
    )
    return Response(
        _enriquecer_convite(request, convite), status=status.HTTP_201_CREATED
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def evento_cerimonial_convite_public_detail_view(request, token):
    try:
        convite = EventoCerimonialConvite.objects.select_related("evento").get(
            token=token,
            ativo=True,
        )
    except EventoCerimonialConvite.DoesNotExist:
        return Response(
            {"error": "Convite inválido ou expirado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "token": str(convite.token),
            "tipo": convite.tipo,
            "tipo_label": convite.get_tipo_display(),
            "evento": {
                "id": convite.evento.id,
                "nome": convite.evento.nome,
                "datetime_inicio": convite.evento.datetime_inicio,
                "datetime_fim": convite.evento.datetime_fim,
            },
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def evento_cerimonial_convite_signup_view(request, token):
    try:
        convite = EventoCerimonialConvite.objects.select_related("evento").get(
            token=token,
            ativo=True,
        )
    except EventoCerimonialConvite.DoesNotExist:
        return Response(
            {"error": "Convite inválido ou expirado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    username = _normalize_username(request.data.get("username"))
    full_name = str(request.data.get("full_name") or "").strip()
    email = str(request.data.get("email") or "").strip().lower()
    cpf_digits = _normalize_cpf(request.data.get("cpf"))
    phone_digits = _normalize_phone(request.data.get("phone"))

    if not username or len(username) < 3:
        return Response(
            {"error": "Nome de usuário inválido."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if User.objects.filter(username=username).exists():
        return Response(
            {"error": "Este nome de usuário já está em uso."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not full_name:
        return Response(
            {"error": "Nome completo é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not email:
        return Response(
            {"error": "E-mail é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if User.objects.filter(email=email).exists():
        return Response(
            {"error": "Este e-mail já está em uso."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(cpf_digits) != 11:
        return Response(
            {"error": "CPF deve conter 11 dígitos."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        validate_cpf(cpf_digits)
    except ValidationError:
        return Response(
            {"error": "CPF inválido."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if User.objects.filter(
        Q(cpf=cpf_digits) | Q(cpf__endswith=cpf_digits)
    ).exists():
        return Response(
            {"error": "Este CPF já está em uso."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not phone_digits:
        return Response(
            {"error": "Telefone é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    temporary_password = User.objects.make_random_password()
    user = User.objects.create_user(
        username=username,
        password=temporary_password,
        full_name=full_name,
        email=email,
        cpf=cpf_digits,
        phone=phone_digits,
        is_active=True,
        first_access=True,
    )

    if convite.tipo == EventoCerimonialConvite.TIPO_ORGANIZADOR:
        group_name = "Organizador do Evento"
        convite.evento.organizadores.add(user)
    else:
        group_name = "Recepção"
        convite.evento.funcionarios.add(user)

    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    user.save()

    if convite.tipo == EventoCerimonialConvite.TIPO_RECEPCAO:
        EventoCerimonialFuncionario.objects.get_or_create(
            evento=convite.evento,
            usuario=user,
            defaults={
                "nome": user.full_name or user.username,
                "documento": cpf_digits,
                "is_recepcao": True,
                "funcao": "Recepção",
                "pagamento_realizado": False,
                "valor_pagamento": 0,
            },
        )

    return Response(
        {
            "message": "Cadastro criado com sucesso.",
            "user_id": str(user.id),
            "username": user.username,
            "temporary_password": temporary_password,
            "group": group_name,
            "evento_id": convite.evento.id,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_funcionarios_cadastro_view(request):
    user = request.user
    if not (
        user.is_staff or user.groups.filter(name="Cerimonialista").exists()
    ):
        return Response(
            {
                "error": "Apenas cerimonialistas podem visualizar funcionários cadastrados."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    queryset = User.objects.all().exclude(id=user.id)
    if not user.is_staff:
        queryset = queryset.filter(created_by=user)

    search = str(request.query_params.get("q") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(full_name__icontains=search)
            | Q(username__icontains=search)
            | Q(cpf__icontains=search)
            | Q(email__icontains=search)
        )

    is_recepcao = request.query_params.get("is_recepcao")
    if is_recepcao is not None and str(is_recepcao).strip() != "":
        if _to_bool(is_recepcao):
            queryset = queryset.filter(groups__name__iexact="Recepção")
        else:
            queryset = queryset.exclude(groups__name__iexact="Recepção")

    queryset = queryset.exclude(groups__name__iexact="Organizador do Evento")
    queryset = queryset.exclude(groups__name__iexact="Cerimonialista")
    queryset = queryset.exclude(groups__name__iexact="Moradores")
    queryset = queryset.exclude(groups__name__iexact="Síndicos")
    queryset = queryset.exclude(groups__name__iexact="Portaria")

    data = []
    for item in queryset.distinct().order_by("full_name")[:200]:
        data.append(
            {
                "id": str(item.id),
                "full_name": item.full_name,
                "username": item.username,
                "email": item.email,
                "cpf": item.cpf,
                "phone": item.phone,
                "is_active": bool(item.is_active),
                "is_recepcao": item.groups.filter(
                    name__iexact="Recepção"
                ).exists(),
            }
        )

    return Response(data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_funcionarios_view(request, pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related(
            "cerimonialistas", "funcionarios"
        ).get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        if not _is_participante_evento(request.user, evento):
            return Response(
                {
                    "error": "Sem permissão para visualizar funcionários deste evento."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        queryset = (
            EventoCerimonialFuncionario.objects.filter(evento=evento)
            .select_related("usuario")
            .prefetch_related("funcoes")
        )
        serializer = EventoCerimonialFuncionarioSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    if not _pode_editar_evento(request.user, evento):
        return Response(
            {
                "error": "Somente cerimonialistas podem editar funcionários do evento."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    payload = request.data.copy()
    usuario_id_payload = payload.get("usuario")
    if usuario_id_payload:
        try:
            usuario_base = User.objects.get(id=usuario_id_payload)
            if not payload.get("nome"):
                payload["nome"] = (
                    usuario_base.full_name or usuario_base.username
                )
            if not payload.get("documento"):
                payload["documento"] = usuario_base.cpf or ""
        except User.DoesNotExist:
            pass

    serializer = EventoCerimonialFuncionarioSerializer(
        data=payload,
        context={"request": request},
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    is_recepcao = bool(serializer.validated_data.get("is_recepcao"))
    usuario = serializer.validated_data.get("usuario")
    usuario_is_active = request.data.get("usuario_is_active")

    try:
        if usuario:
            usuario_result = _vincular_usuario_existente(
                request,
                usuario=usuario,
                is_recepcao=is_recepcao,
                usuario_is_active=usuario_is_active,
            )
        else:
            usuario_result = _criar_usuario_funcionario(
                request,
                nome=serializer.validated_data.get("nome"),
                documento=serializer.validated_data.get("documento"),
                email=request.data.get("email"),
                phone=request.data.get("phone"),
                is_recepcao=is_recepcao,
            )

        usuario = usuario_result["usuario"]
    except ValidationError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    nome = str(serializer.validated_data.get("nome") or "").strip() or (
        usuario.full_name or usuario.username
    )
    documento = str(
        serializer.validated_data.get("documento") or ""
    ).strip() or str(usuario.cpf or "")

    funcionario = serializer.save(
        evento=evento,
        usuario=usuario,
        nome=nome,
        documento=documento,
        is_recepcao=is_recepcao,
    )

    if is_recepcao:
        evento.funcionarios.add(usuario)

    response_data = EventoCerimonialFuncionarioSerializer(
        funcionario,
        context={"request": request},
    ).data
    response_data["usuario_email_enviado"] = usuario_result["email_enviado"]
    response_data["usuario_email_erro"] = usuario_result["email_erro"]
    response_data["usuario_ativado"] = usuario_result["ativado"]

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_funcionario_detail_view(request, pk, funcionario_pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related(
            "cerimonialistas", "funcionarios"
        ).get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        funcionario = (
            EventoCerimonialFuncionario.objects.select_related("usuario")
            .prefetch_related("funcoes")
            .get(pk=funcionario_pk, evento=evento)
        )
    except EventoCerimonialFuncionario.DoesNotExist:
        return Response(
            {"error": "Funcionário do evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        if not _is_participante_evento(request.user, evento):
            return Response(
                {"error": "Sem permissão para visualizar este funcionário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            EventoCerimonialFuncionarioSerializer(
                funcionario,
                context={"request": request},
            ).data
        )

    if not _pode_editar_evento(request.user, evento):
        return Response(
            {
                "error": "Somente cerimonialistas podem editar funcionários do evento."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "PATCH":
        serializer = EventoCerimonialFuncionarioSerializer(
            funcionario,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        is_recepcao = bool(
            serializer.validated_data.get(
                "is_recepcao", funcionario.is_recepcao
            )
        )
        usuario = serializer.validated_data.get("usuario", funcionario.usuario)
        usuario_is_active = request.data.get("usuario_is_active")

        usuario_result = {
            "usuario": usuario,
            "email_enviado": False,
            "email_erro": None,
            "ativado": False,
        }

        if usuario:
            try:
                usuario_result = _vincular_usuario_existente(
                    request,
                    usuario=usuario,
                    is_recepcao=is_recepcao,
                    usuario_is_active=usuario_is_active,
                )
            except ValidationError as exc:
                return Response(
                    {"error": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        nome = str(serializer.validated_data.get("nome") or "").strip() or (
            usuario.full_name if usuario else funcionario.nome
        )
        documento = str(
            serializer.validated_data.get("documento") or ""
        ).strip() or (
            str(usuario.cpf or "") if usuario else funcionario.documento
        )

        funcionario = serializer.save(
            usuario=usuario,
            nome=nome,
            documento=documento,
            is_recepcao=is_recepcao,
        )

        if is_recepcao and usuario:
            evento.funcionarios.add(usuario)

        response_data = EventoCerimonialFuncionarioSerializer(
            funcionario,
            context={"request": request},
        ).data
        response_data["usuario_email_enviado"] = usuario_result[
            "email_enviado"
        ]
        response_data["usuario_email_erro"] = usuario_result["email_erro"]
        response_data["usuario_ativado"] = usuario_result["ativado"]

        return Response(response_data)

    funcionario.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def funcao_festa_list_create_view(request):
    user = request.user
    if not (
        user.is_staff or user.groups.filter(name="Cerimonialista").exists()
    ):
        return Response(
            {
                "error": "Apenas cerimonialistas podem gerenciar funções de festa."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        queryset = FuncaoFesta.objects.all()
        if not user.is_staff:
            queryset = queryset.filter(created_by=user)

        search = str(request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(nome__icontains=search)

        ativo = request.query_params.get("ativo")
        if ativo is not None and str(ativo).strip() != "":
            queryset = queryset.filter(ativo=_to_bool(ativo))

        serializer = FuncaoFestaSerializer(
            queryset.order_by("nome"), many=True
        )
        return Response(serializer.data)

    itens = request.data.get("itens")
    if isinstance(itens, list):
        created = []
        errors = []
        nomes_payload = set()

        for index, item in enumerate(itens):
            if not isinstance(item, dict):
                errors.append(
                    {
                        "index": index,
                        "error": "Formato inválido. Informe objeto com nome e ativo.",
                    }
                )
                continue

            nome = str(item.get("nome") or "").strip()
            if not nome:
                errors.append(
                    {"index": index, "error": "Nome da função é obrigatório."}
                )
                continue

            nome_norm = nome.lower()
            if nome_norm in nomes_payload:
                errors.append(
                    {
                        "index": index,
                        "error": "Função duplicada na lista enviada.",
                    }
                )
                continue
            nomes_payload.add(nome_norm)

            conflito = FuncaoFesta.objects.filter(nome__iexact=nome)
            if not user.is_staff:
                conflito = conflito.filter(created_by=user)
            if conflito.exists():
                errors.append(
                    {
                        "index": index,
                        "error": "Já existe uma função com este nome.",
                    }
                )
                continue

            funcao = FuncaoFesta.objects.create(
                nome=nome,
                ativo=_to_bool(item.get("ativo"), default=True),
                created_by=None if user.is_staff else user,
                updated_by=user,
            )
            created.append(FuncaoFestaSerializer(funcao).data)

        if not created:
            return Response(
                {
                    "error": "Nenhuma função foi criada.",
                    "errors": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "created": created,
                "errors": errors,
            },
            status=status.HTTP_201_CREATED,
        )

    nome = str(request.data.get("nome") or "").strip()
    if not nome:
        return Response(
            {"error": "Nome da função é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    queryset = FuncaoFesta.objects.filter(nome__iexact=nome)
    if not user.is_staff:
        queryset = queryset.filter(created_by=user)
    if queryset.exists():
        return Response(
            {"error": "Já existe uma função com este nome."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    funcao = FuncaoFesta.objects.create(
        nome=nome,
        ativo=_to_bool(request.data.get("ativo"), default=True),
        created_by=None if user.is_staff else user,
        updated_by=user,
    )

    return Response(
        FuncaoFestaSerializer(funcao).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def funcao_festa_detail_view(request, funcao_pk):
    user = request.user
    if not (
        user.is_staff or user.groups.filter(name="Cerimonialista").exists()
    ):
        return Response(
            {
                "error": "Apenas cerimonialistas podem gerenciar funções de festa."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        queryset = FuncaoFesta.objects.all()
        if not user.is_staff:
            queryset = queryset.filter(created_by=user)
        funcao = queryset.get(pk=funcao_pk)
    except FuncaoFesta.DoesNotExist:
        return Response(
            {"error": "Função não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(FuncaoFestaSerializer(funcao).data)

    if request.method == "PATCH":
        nome = request.data.get("nome")
        if nome is not None:
            nome = str(nome).strip()
            if not nome:
                return Response(
                    {"error": "Nome da função é obrigatório."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            conflito = FuncaoFesta.objects.filter(nome__iexact=nome).exclude(
                id=funcao.id
            )
            if not user.is_staff:
                conflito = conflito.filter(created_by=user)
            if conflito.exists():
                return Response(
                    {"error": "Já existe uma função com este nome."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            funcao.nome = nome

        if "ativo" in request.data:
            funcao.ativo = _to_bool(request.data.get("ativo"), default=True)

        funcao.updated_by = user
        funcao.save()
        return Response(FuncaoFestaSerializer(funcao).data)

    funcao.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


__all__ = [
    "evento_cerimonial_convites_list_view",
    "evento_cerimonial_convite_generate_view",
    "evento_cerimonial_convite_public_detail_view",
    "evento_cerimonial_convite_signup_view",
    "evento_cerimonial_funcionarios_cadastro_view",
    "evento_cerimonial_funcionarios_view",
    "evento_cerimonial_funcionario_detail_view",
    "funcao_festa_list_create_view",
    "funcao_festa_detail_view",
]
