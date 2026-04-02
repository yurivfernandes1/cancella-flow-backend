from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import (
    ConvidadoListaCerimonial,
    EventoCerimonial,
    EventoCerimonialFuncionario,
)
from ..serializers.evento_cerimonial_serializer import (
    EventoCerimonialListSerializer,
)
from .evento_cerimonial_views import _is_recepcao


def _agora_local():
    return timezone.localtime()


def _evento_no_mesmo_dia(evento, referencia=None):
    if not evento.datetime_inicio and not evento.datetime_fim:
        return False

    referencia = referencia or _agora_local()
    data_ref = referencia.date()

    inicio_local = (
        timezone.localtime(evento.datetime_inicio)
        if evento.datetime_inicio
        else None
    )
    fim_local = (
        timezone.localtime(evento.datetime_fim)
        if evento.datetime_fim
        else inicio_local
    )

    if inicio_local and fim_local and fim_local < inicio_local:
        fim_local = inicio_local

    if inicio_local and fim_local:
        return inicio_local.date() <= data_ref <= fim_local.date()

    base = inicio_local or fim_local
    return bool(base and base.date() == data_ref)


def _evento_em_andamento(evento, referencia=None):
    if not evento.datetime_inicio or not evento.datetime_fim:
        return False
    referencia = referencia or _agora_local()
    inicio_local = timezone.localtime(evento.datetime_inicio)
    fim_local = timezone.localtime(evento.datetime_fim)
    return inicio_local <= referencia <= fim_local


def _pode_operar_evento_recepcao(user, evento):
    if user.is_staff:
        return True
    return (
        _is_recepcao(user) and evento.funcionarios.filter(id=user.id).exists()
    )


def _vinculo_evento(user, evento):
    return (
        EventoCerimonialFuncionario.objects.filter(evento=evento, usuario=user)
        .order_by("-is_recepcao", "-id")
        .first()
    )


def _vinculo_ativo(user):
    _encerrar_vinculos_ativos_expirados(user)
    return (
        EventoCerimonialFuncionario.objects.select_related("evento")
        .filter(
            usuario=user,
            horario_entrada__isnull=False,
            horario_saida__isnull=True,
        )
        .order_by("-horario_entrada", "-id")
        .first()
    )


def _encerrar_vinculos_ativos_expirados(user):
    referencia = _agora_local()
    vinculos_abertos = (
        EventoCerimonialFuncionario.objects.select_related("evento")
        .filter(
            usuario=user,
            horario_entrada__isnull=False,
            horario_saida__isnull=True,
        )
        .order_by("-horario_entrada", "-id")
    )

    for vinculo in vinculos_abertos:
        evento = getattr(vinculo, "evento", None)
        if not evento or not evento.datetime_fim:
            continue

        fim_local = timezone.localtime(evento.datetime_fim)
        if fim_local >= referencia:
            continue

        horario_saida = fim_local
        if vinculo.horario_entrada and horario_saida < vinculo.horario_entrada:
            horario_saida = referencia

        vinculo.horario_saida = horario_saida
        vinculo.save(update_fields=["horario_saida", "updated_at"])


def _serializar_contatos_cerimonial(evento):
    contatos = []
    for cerimonialista in evento.cerimonialistas.all():
        contatos.append(
            {
                "id": str(cerimonialista.id),
                "nome": cerimonialista.full_name or cerimonialista.username,
                "telefone": cerimonialista.phone or "",
            }
        )

    principal = None
    for contato in contatos:
        if contato["telefone"]:
            principal = contato
            break

    if principal is None and contatos:
        principal = contatos[0]

    return principal, contatos


def _erro_sem_vinculo_recepcao():
    return Response(
        {
            "error": "Seu usuário não possui vínculo operacional de recepção neste evento."
        },
        status=status.HTTP_409_CONFLICT,
    )


def _documento_vinculo_para_usuario(user):
    cpf = "".join(
        ch for ch in str(getattr(user, "cpf", "") or "") if ch.isdigit()
    )
    if cpf:
        return cpf
    user_id_compacto = "".join(ch for ch in str(user.id) if ch.isalnum())
    return (user_id_compacto or "recepcao")[:14]


def _documento_vinculo_unico_no_evento(user, evento, documento_base):
    documento = str(documento_base or "").strip()[:14]
    if not documento:
        return None

    conflito = EventoCerimonialFuncionario.objects.filter(
        evento=evento,
        documento=documento,
    ).exclude(usuario=user)
    if not conflito.exists():
        return documento

    user_id_compacto = "".join(ch for ch in str(user.id) if ch.isalnum())
    sufixo_base = (user_id_compacto or "usr")[-6:]
    prefixo = "".join(ch for ch in documento if ch.isdigit()) or documento

    candidato = f"{prefixo[: max(1, 14 - len(sufixo_base))]}{sufixo_base}"[:14]
    conflito_candidato = EventoCerimonialFuncionario.objects.filter(
        evento=evento,
        documento=candidato,
    ).exclude(usuario=user)
    if not conflito_candidato.exists():
        return candidato

    for idx in range(1, 100):
        sufixo = f"{sufixo_base}{idx}"[-6:]
        candidato = f"{prefixo[: max(1, 14 - len(sufixo))]}{sufixo}"[:14]
        conflito_candidato = EventoCerimonialFuncionario.objects.filter(
            evento=evento,
            documento=candidato,
        ).exclude(usuario=user)
        if not conflito_candidato.exists():
            return candidato

    return None


def _garantir_vinculo_recepcao(user, evento):
    vinculo = _vinculo_evento(user, evento)
    if vinculo:
        return vinculo

    if user.is_staff:
        return vinculo

    if not _is_recepcao(user):
        return None

    if not evento.funcionarios.filter(id=user.id).exists():
        return None

    nome_base = (user.full_name or user.username or "Recepção").strip()
    documento_base = _documento_vinculo_para_usuario(user)
    documento_para_criar = _documento_vinculo_unico_no_evento(
        user, evento, documento_base
    )
    if not documento_para_criar:
        return None

    try:
        vinculo, _ = EventoCerimonialFuncionario.objects.get_or_create(
            evento=evento,
            usuario=user,
            defaults={
                "nome": nome_base,
                "documento": documento_para_criar,
                "is_recepcao": True,
                "funcao": "Recepção",
                "pagamento_realizado": False,
                "valor_pagamento": 0,
            },
        )
    except IntegrityError:
        vinculo = _vinculo_evento(user, evento)
        if not vinculo:
            candidato = (
                EventoCerimonialFuncionario.objects.filter(
                    evento=evento,
                    documento=documento_para_criar,
                )
                .order_by("-id")
                .first()
            )
            if candidato and (
                candidato.usuario_id is None or candidato.usuario_id == user.id
            ):
                candidato.usuario = user
                candidato.save(update_fields=["usuario", "updated_at"])
                vinculo = candidato

    if not vinculo:
        return None

    campos_update = []
    if not vinculo.is_recepcao:
        vinculo.is_recepcao = True
        campos_update.append("is_recepcao")
    if not (vinculo.nome or "").strip():
        vinculo.nome = nome_base
        campos_update.append("nome")
    if not (vinculo.documento or "").strip():
        vinculo.documento = documento_base
        campos_update.append("documento")
    if vinculo.usuario_id != user.id:
        vinculo.usuario = user
        campos_update.append("usuario")

    if campos_update:
        campos_update.append("updated_at")
        vinculo.save(update_fields=campos_update)

    return vinculo


def _validar_operacao_evento_recepcao(user, evento, requer_horario=False):
    if not _pode_operar_evento_recepcao(user, evento):
        return (
            Response(
                {
                    "error": "Sem permissão para operar este evento na recepção."
                },
                status=status.HTTP_403_FORBIDDEN,
            ),
            None,
            None,
        )

    vinculo = _garantir_vinculo_recepcao(user, evento)
    if vinculo is None and not user.is_staff:
        return _erro_sem_vinculo_recepcao(), None, None

    referencia = _agora_local()

    if user.is_staff:
        return None, vinculo, referencia

    ativo = _vinculo_ativo(user)
    if not ativo:
        return (
            Response(
                {
                    "error": "Faça check-in no evento para iniciar as operações da recepção."
                },
                status=status.HTTP_403_FORBIDDEN,
            ),
            None,
            None,
        )

    if ativo.evento_id != evento.id:
        return (
            Response(
                {
                    "error": "Você já possui check-in ativo em outro evento.",
                    "evento_ativo": ativo.evento.nome,
                    "evento_ativo_id": ativo.evento_id,
                },
                status=status.HTTP_409_CONFLICT,
            ),
            None,
            None,
        )

    if requer_horario and not _evento_em_andamento(evento, referencia):
        return (
            Response(
                {
                    "error": "Esta operação só é permitida durante o horário do evento."
                },
                status=status.HTTP_400_BAD_REQUEST,
            ),
            None,
            None,
        )

    return None, vinculo, referencia


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recepcao_eventos_painel_view(request):
    user = request.user
    if not (_is_recepcao(user) or user.is_staff):
        return Response(
            {"error": "Acesso permitido apenas para recepção."},
            status=status.HTTP_403_FORBIDDEN,
        )

    eventos = list(
        EventoCerimonial.objects.select_related("lista_convidados")
        .prefetch_related("cerimonialistas", "funcionarios")
        .filter(funcionarios=user)
        .distinct()
        .order_by("datetime_inicio")
    )

    referencia = _agora_local()
    vinculos = (
        EventoCerimonialFuncionario.objects.filter(
            usuario=user,
            evento__in=eventos,
        )
        .select_related("evento")
        .order_by("-horario_entrada", "-id")
    )

    vinculo_por_evento = {}
    for vinculo in vinculos:
        vinculo_por_evento.setdefault(vinculo.evento_id, vinculo)

    ativo = _vinculo_ativo(user)
    evento_ativo_id = ativo.evento_id if ativo else None

    base = EventoCerimonialListSerializer(
        eventos,
        many=True,
        context={"request": request},
    ).data

    eventos_data = []
    evento_hoje_id = None
    for item in base:
        evento_id = item["id"]
        evento = next((e for e in eventos if e.id == evento_id), None)
        if not evento:
            continue

        vinculo = vinculo_por_evento.get(evento_id)
        checkin_realizado = bool(vinculo and vinculo.horario_entrada)
        checkout_realizado = bool(vinculo and vinculo.horario_saida)
        checkin_ativo = (
            checkin_realizado
            and not checkout_realizado
            and evento_ativo_id == evento_id
        )

        is_hoje = _evento_no_mesmo_dia(evento, referencia)
        is_em_andamento = _evento_em_andamento(evento, referencia)

        if is_hoje and evento_hoje_id is None:
            evento_hoje_id = evento_id

        contato_principal, contatos = _serializar_contatos_cerimonial(evento)

        eventos_data.append(
            {
                **item,
                "is_hoje": is_hoje,
                "is_em_andamento": is_em_andamento,
                "can_checkin_today": is_hoje
                and not checkin_realizado
                and (evento_ativo_id in (None, evento_id)),
                "can_checkout": checkin_ativo,
                "can_read_qr": checkin_ativo and is_em_andamento,
                "can_consultar_lista": checkin_ativo and is_em_andamento,
                "checkin_realizado": checkin_realizado,
                "checkout_realizado": checkout_realizado,
                "horario_entrada": (
                    vinculo.horario_entrada if vinculo else None
                ),
                "horario_saida": vinculo.horario_saida if vinculo else None,
                "contato_cerimonial": contato_principal,
                "contatos_cerimonial": contatos,
            }
        )

    return Response(
        {
            "eventos": eventos_data,
            "evento_ativo_id": evento_ativo_id,
            "tem_evento_hoje": evento_hoje_id is not None,
            "evento_hoje_id": evento_hoje_id,
            "can_read_qr_global": bool(
                ativo and _evento_em_andamento(ativo.evento, referencia)
            ),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recepcao_evento_checkin_view(request, pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related("funcionarios").get(
            pk=pk
        )
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_operar_evento_recepcao(request.user, evento):
        return Response(
            {"error": "Sem permissão para operar este evento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    referencia = _agora_local()
    if not _evento_no_mesmo_dia(evento, referencia):
        return Response(
            {"error": "O check-in só pode ser feito no mesmo dia do evento."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    vinculo = _garantir_vinculo_recepcao(request.user, evento)
    if vinculo is None and not request.user.is_staff:
        return _erro_sem_vinculo_recepcao()

    ativo = _vinculo_ativo(request.user)
    if ativo and ativo.evento_id != evento.id:
        return Response(
            {
                "error": "Finalize o checkout do evento em andamento antes de iniciar outro.",
                "evento_ativo": ativo.evento.nome,
                "evento_ativo_id": ativo.evento_id,
            },
            status=status.HTTP_409_CONFLICT,
        )

    if vinculo and vinculo.horario_entrada and not vinculo.horario_saida:
        return Response(
            {
                "error": "Check-in já foi realizado para este evento.",
                "horario_entrada": vinculo.horario_entrada,
            },
            status=status.HTTP_409_CONFLICT,
        )

    if vinculo and vinculo.horario_entrada and vinculo.horario_saida:
        return Response(
            {
                "error": "Check-in e checkout já foram finalizados para este evento.",
                "horario_entrada": vinculo.horario_entrada,
                "horario_saida": vinculo.horario_saida,
            },
            status=status.HTTP_409_CONFLICT,
        )

    if vinculo:
        vinculo.horario_entrada = referencia
        vinculo.horario_saida = None
        vinculo.save(
            update_fields=["horario_entrada", "horario_saida", "updated_at"]
        )

    return Response(
        {
            "success": True,
            "message": "Check-in realizado com sucesso.",
            "evento_id": evento.id,
            "evento_nome": evento.nome,
            "horario_entrada": referencia,
            "horario_saida": None,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recepcao_evento_checkout_view(request, pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related("funcionarios").get(
            pk=pk
        )
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_operar_evento_recepcao(request.user, evento):
        return Response(
            {"error": "Sem permissão para operar este evento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    vinculo = _garantir_vinculo_recepcao(request.user, evento)
    if vinculo is None and not request.user.is_staff:
        return _erro_sem_vinculo_recepcao()

    if not vinculo or not vinculo.horario_entrada:
        return Response(
            {"error": "Check-in não encontrado para este evento."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if vinculo.horario_saida:
        return Response(
            {
                "error": "Checkout já foi realizado para este evento.",
                "horario_entrada": vinculo.horario_entrada,
                "horario_saida": vinculo.horario_saida,
            },
            status=status.HTTP_409_CONFLICT,
        )

    ativo = _vinculo_ativo(request.user)
    if ativo and ativo.evento_id != evento.id:
        return Response(
            {
                "error": "Há um check-in ativo em outro evento.",
                "evento_ativo": ativo.evento.nome,
                "evento_ativo_id": ativo.evento_id,
            },
            status=status.HTTP_409_CONFLICT,
        )

    referencia = _agora_local()
    vinculo.horario_saida = referencia
    vinculo.save(update_fields=["horario_saida", "updated_at"])

    minutos_trabalhados = 0
    if vinculo.horario_entrada:
        delta = referencia - timezone.localtime(vinculo.horario_entrada)
        minutos_trabalhados = max(int(delta.total_seconds() // 60), 0)

    return Response(
        {
            "success": True,
            "message": "Checkout realizado com sucesso.",
            "evento_id": evento.id,
            "evento_nome": evento.nome,
            "horario_entrada": vinculo.horario_entrada,
            "horario_saida": vinculo.horario_saida,
            "minutos_trabalhados": minutos_trabalhados,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recepcao_evento_convidados_view(request, pk):
    try:
        evento = EventoCerimonial.objects.select_related("lista_convidados")
        evento = evento.prefetch_related("funcionarios").get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    erro, _, _ = _validar_operacao_evento_recepcao(
        request.user,
        evento,
        requer_horario=True,
    )
    if erro:
        return erro

    lista = getattr(evento, "lista_convidados", None)
    if not lista:
        return Response(
            {"error": "Lista de convidados não encontrada para este evento."},
            status=status.HTTP_404_NOT_FOUND,
        )

    search = str(request.query_params.get("q") or "").strip()
    convidados = ConvidadoListaCerimonial.objects.filter(lista=lista)
    if search:
        convidados = convidados.filter(nome__icontains=search)

    convidados = convidados.order_by("-vip", "nome", "id")[:120]

    data = [
        {
            "id": convidado.id,
            "nome": convidado.nome,
            "cpf_mascarado": (
                f"{convidado.cpf[:3]}*****{convidado.cpf[-3:]}"
                if len(convidado.cpf or "") == 11
                else convidado.cpf
            ),
            "vip": convidado.vip,
            "entrada_confirmada": convidado.entrada_confirmada,
            "entrada_em": convidado.entrada_em,
        }
        for convidado in convidados
    ]

    return Response(
        {
            "evento_id": evento.id,
            "evento_nome": evento.nome,
            "total": len(data),
            "results": data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recepcao_evento_confirmar_por_nome_view(request, pk):
    try:
        evento = EventoCerimonial.objects.select_related("lista_convidados")
        evento = evento.prefetch_related("funcionarios").get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    erro, _, referencia = _validar_operacao_evento_recepcao(
        request.user,
        evento,
        requer_horario=True,
    )
    if erro:
        return erro

    nome_input = " ".join(
        str(request.data.get("nome_completo") or "").strip().split()
    )
    if not nome_input:
        return Response(
            {"error": "Informe o nome completo do convidado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lista = getattr(evento, "lista_convidados", None)
    if not lista:
        return Response(
            {"error": "Lista de convidados não encontrada para este evento."},
            status=status.HTTP_404_NOT_FOUND,
        )

    queryset = ConvidadoListaCerimonial.objects.filter(
        lista=lista,
        nome__iexact=nome_input,
    ).order_by("id")

    total = queryset.count()
    if total == 0:
        return Response(
            {
                "error": "Nome não encontrado na lista deste evento. Digite o nome completo conforme o convite."
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if total > 1:
        return Response(
            {
                "error": "Mais de um convidado com este nome foi encontrado. Utilize o QR Code para confirmar a entrada."
            },
            status=status.HTTP_409_CONFLICT,
        )

    convidado = queryset.first()
    if convidado.entrada_confirmada:
        return Response(
            {
                "aviso": "Convidado já confirmou a entrada anteriormente.",
                "nome": convidado.nome,
                "entrada_em": convidado.entrada_em,
            }
        )

    convidado.entrada_confirmada = True
    convidado.entrada_em = referencia
    convidado.save(update_fields=["entrada_confirmada", "entrada_em"])

    cpf = convidado.cpf or ""
    cpf_mascarado = f"{cpf[:3]}*****{cpf[-3:]}" if len(cpf) == 11 else cpf

    return Response(
        {
            "success": True,
            "message": "Entrada confirmada com sucesso.",
            "nome": convidado.nome,
            "cpf_mascarado": cpf_mascarado,
            "entrada_em": convidado.entrada_em,
        }
    )


__all__ = [
    "recepcao_eventos_painel_view",
    "recepcao_evento_checkin_view",
    "recepcao_evento_checkout_view",
    "recepcao_evento_convidados_view",
    "recepcao_evento_confirmar_por_nome_view",
]
