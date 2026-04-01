import base64
from io import BytesIO

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
)
from ..serializers.evento_cerimonial_aux_serializer import (
    EventoCerimonialConviteSerializer,
    EventoCerimonialFuncionarioSerializer,
)
from .evento_cerimonial_views import _is_participante_evento, _pode_editar_evento


def _frontend_base(request):
    base = (
        getattr(django_settings, "FRONTEND_BASE_URL", "")
        or request.headers.get("Origin")
        or "https://cancellaflow.com.br"
    )
    return str(base).rstrip("/")


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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_convites_list_view(request, pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related("cerimonialistas").get(pk=pk)
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

    convites = EventoCerimonialConvite.objects.filter(evento=evento, ativo=True)
    return Response([_enriquecer_convite(request, c) for c in convites])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_convite_generate_view(request, pk, tipo):
    try:
        evento = EventoCerimonial.objects.prefetch_related("cerimonialistas").get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_editar_evento(request.user, evento):
        return Response(
            {"error": "Somente cerimonialistas podem gerar convites do evento."},
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
    return Response(_enriquecer_convite(request, convite), status=status.HTTP_201_CREATED)


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
    if User.objects.filter(Q(cpf=cpf_digits) | Q(cpf__endswith=cpf_digits)).exists():
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_funcionarios_view(request, pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related("cerimonialistas", "funcionarios").get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        if not _is_participante_evento(request.user, evento):
            return Response(
                {"error": "Sem permissão para visualizar funcionários deste evento."},
                status=status.HTTP_403_FORBIDDEN,
            )
        queryset = EventoCerimonialFuncionario.objects.filter(evento=evento).select_related("usuario")
        serializer = EventoCerimonialFuncionarioSerializer(queryset, many=True)
        return Response(serializer.data)

    if not _pode_editar_evento(request.user, evento):
        return Response(
            {"error": "Somente cerimonialistas podem editar funcionários do evento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = EventoCerimonialFuncionarioSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    usuario = serializer.validated_data.get("usuario")
    if usuario and not usuario.groups.filter(name__iexact="Recepção").exists():
        return Response(
            {"error": "O usuário selecionado não pertence ao grupo Recepção."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    funcionario = serializer.save(evento=evento)
    if usuario:
        evento.funcionarios.add(usuario)

    return Response(
        EventoCerimonialFuncionarioSerializer(funcionario).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_funcionario_detail_view(request, pk, funcionario_pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related("cerimonialistas", "funcionarios").get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        funcionario = EventoCerimonialFuncionario.objects.get(pk=funcionario_pk, evento=evento)
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
        return Response(EventoCerimonialFuncionarioSerializer(funcionario).data)

    if not _pode_editar_evento(request.user, evento):
        return Response(
            {"error": "Somente cerimonialistas podem editar funcionários do evento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "PATCH":
        serializer = EventoCerimonialFuncionarioSerializer(
            funcionario,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.validated_data.get("usuario")
        if usuario and not usuario.groups.filter(name__iexact="Recepção").exists():
            return Response(
                {"error": "O usuário selecionado não pertence ao grupo Recepção."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        funcionario = serializer.save()
        if usuario:
            evento.funcionarios.add(usuario)

        return Response(EventoCerimonialFuncionarioSerializer(funcionario).data)

    funcionario.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


__all__ = [
    "evento_cerimonial_convites_list_view",
    "evento_cerimonial_convite_generate_view",
    "evento_cerimonial_convite_public_detail_view",
    "evento_cerimonial_convite_signup_view",
    "evento_cerimonial_funcionarios_view",
    "evento_cerimonial_funcionario_detail_view",
]
