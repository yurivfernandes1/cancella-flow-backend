import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Ocorrencia
from ..serializers import (
    OcorrenciaCreateSerializer,
    OcorrenciaRespostaSerializer,
    OcorrenciaSerializer,
)

logger = logging.getLogger(__name__)


def _is_sindico_or_staff(user):
    return (
        user.is_staff
        or user.groups.filter(
            Q(name__iexact="Síndicos") | Q(name__iexact="Sindicos")
        ).exists()
    )


def _get_condominio(user):
    return getattr(user, "condominio", None)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ocorrencia_list_view(request):
    """
    Lista ocorrências:
    - Síndico/is_staff: todas do condomínio, com filtros por status e tipo
    - Morador/Portaria: apenas as que criaram
    """
    try:
        user = request.user

        if _is_sindico_or_staff(user):
            condominio = _get_condominio(user)
            qs = Ocorrencia.objects.select_related(
                "criado_por", "respondido_por"
            ).filter(criado_por__condominio=condominio)
        else:
            qs = Ocorrencia.objects.select_related(
                "criado_por", "respondido_por"
            ).filter(criado_por=user)

        status_filter = request.GET.get("status")
        incluir_finalizadas = request.GET.get("incluir_finalizadas")

        if status_filter:
            qs = qs.filter(status=status_filter)
        elif not incluir_finalizadas:
            qs = qs.exclude(status__in=["resolvida", "fechada"])

        tipo_filter = request.GET.get("tipo")
        if tipo_filter:
            qs = qs.filter(tipo=tipo_filter)

        qs = qs.order_by("-created_at")

        serializer = OcorrenciaSerializer(qs, many=True)
        return Response(serializer.data)

    except Exception as e:
        logger.exception("Erro ao listar ocorrências")
        return Response(
            {"error": f"Erro ao listar ocorrências: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ocorrencia_create_view(request):
    """
    Cria uma ocorrência. Permitido apenas para Moradores e Portaria.
    """
    try:
        user = request.user
        is_morador = user.groups.filter(name="Moradores").exists()
        is_portaria = user.groups.filter(name="Portaria").exists()

        if not (is_morador or is_portaria or user.is_staff):
            return Response(
                {
                    "error": "Apenas moradores e porteiros podem abrir ocorrências."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = OcorrenciaCreateSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            ocorrencia = serializer.save()
            return Response(
                OcorrenciaSerializer(ocorrencia).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.exception("Erro ao criar ocorrência")
        return Response(
            {"error": f"Erro ao criar ocorrência: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ocorrencia_detail_view(request, pk):
    """
    Retorna detalhe de uma ocorrência.
    - Síndico/is_staff: qualquer do condomínio
    - Outros: apenas as próprias
    """
    try:
        user = request.user
        ocorrencia = Ocorrencia.objects.select_related(
            "criado_por", "respondido_por"
        ).get(pk=pk)

        if _is_sindico_or_staff(user):
            condominio = _get_condominio(user)
            if condominio and ocorrencia.criado_por.condominio != condominio:
                return Response(
                    {
                        "error": "Você não tem permissão para ver esta ocorrência."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            if ocorrencia.criado_por != user:
                return Response(
                    {
                        "error": "Você não tem permissão para ver esta ocorrência."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = OcorrenciaSerializer(ocorrencia)
        return Response(serializer.data)

    except Ocorrencia.DoesNotExist:
        return Response(
            {"error": "Ocorrência não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception("Erro ao buscar ocorrência")
        return Response(
            {"error": f"Erro ao buscar ocorrência: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def ocorrencia_update_view(request, pk):
    """
    Atualiza uma ocorrência.
    - Morador/Portaria: pode editar titulo e descricao enquanto status == 'aberta'
    - Síndico/is_staff: usa OcorrenciaRespostaSerializer para responder e mudar status
    """
    try:
        user = request.user
        ocorrencia = Ocorrencia.objects.get(pk=pk)

        if _is_sindico_or_staff(user):
            condominio = _get_condominio(user)
            if condominio and ocorrencia.criado_por.condominio != condominio:
                return Response(
                    {
                        "error": "Você não tem permissão para atualizar esta ocorrência."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            serializer = OcorrenciaRespostaSerializer(
                ocorrencia, data=request.data, partial=True
            )
            if serializer.is_valid():
                serializer.save(
                    respondido_por=user,
                    respondido_em=timezone.now(),
                )
                return Response(OcorrenciaSerializer(ocorrencia).data)
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        else:
            if ocorrencia.criado_por != user:
                return Response(
                    {
                        "error": "Você não tem permissão para atualizar esta ocorrência."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            requested_status = request.data.get("status")
            motivo_reabertura = (
                request.data.get("motivo_reabertura") or ""
            ).strip()

            # Morador/Portaria podem reabrir ocorrencia resolvida para
            # em_andamento, com justificativa, dentro de 5 dias da resolução.
            if requested_status == Ocorrencia.STATUS_EM_ANDAMENTO:
                if ocorrencia.status != Ocorrencia.STATUS_RESOLVIDA:
                    return Response(
                        {
                            "error": "Apenas ocorrências resolvidas podem ser reabertas."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if not motivo_reabertura:
                    return Response(
                        {
                            "error": "Informe a justificativa para reabrir a ocorrência."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                referencia_resolucao = (
                    ocorrencia.respondido_em or ocorrencia.updated_at
                )
                if not referencia_resolucao:
                    return Response(
                        {
                            "error": "Não foi possível validar a data de resolução da ocorrência."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if timezone.now() - referencia_resolucao > timedelta(days=5):
                    return Response(
                        {
                            "error": "A ocorrência só pode ser reaberta até 5 dias após a resolução."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                ocorrencia.status = Ocorrencia.STATUS_EM_ANDAMENTO
                ocorrencia.motivo_reabertura = motivo_reabertura
                ocorrencia.reaberto_por = user
                ocorrencia.reaberto_em = timezone.now()
                ocorrencia.save(
                    update_fields=[
                        "status",
                        "motivo_reabertura",
                        "reaberto_por",
                        "reaberto_em",
                        "updated_at",
                    ]
                )
                return Response(OcorrenciaSerializer(ocorrencia).data)

            if ocorrencia.status != Ocorrencia.STATUS_ABERTA:
                return Response(
                    {
                        "error": "Só é possível editar ocorrências com status 'aberta'."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            allowed_fields = {"titulo", "descricao"}
            data = {
                k: v for k, v in request.data.items() if k in allowed_fields
            }
            serializer = OcorrenciaCreateSerializer(
                ocorrencia, data=data, partial=True
            )
            if serializer.is_valid():
                serializer.save()
                return Response(OcorrenciaSerializer(ocorrencia).data)
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

    except Ocorrencia.DoesNotExist:
        return Response(
            {"error": "Ocorrência não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception("Erro ao atualizar ocorrência")
        return Response(
            {"error": f"Erro ao atualizar ocorrência: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def ocorrencia_delete_view(request, pk):
    """
    Exclui uma ocorrência.
    - Criador (enquanto status=aberta) ou Síndico/is_staff
    """
    try:
        user = request.user
        ocorrencia = Ocorrencia.objects.get(pk=pk)

        if _is_sindico_or_staff(user):
            condominio = _get_condominio(user)
            if condominio and ocorrencia.criado_por.condominio != condominio:
                return Response(
                    {
                        "error": "Você não tem permissão para excluir esta ocorrência."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            if ocorrencia.criado_por != user:
                return Response(
                    {
                        "error": "Você não tem permissão para excluir esta ocorrência."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            if ocorrencia.status != Ocorrencia.STATUS_ABERTA:
                return Response(
                    {
                        "error": "Só é possível excluir ocorrências com status 'aberta'."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        ocorrencia.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    except Ocorrencia.DoesNotExist:
        return Response(
            {"error": "Ocorrência não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception("Erro ao excluir ocorrência")
        return Response(
            {"error": f"Erro ao excluir ocorrência: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
