from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import EventoCerimonial, ListaConvidadosCerimonial
from ..serializers.evento_cerimonial_serializer import (
    EventoCerimonialListSerializer,
    EventoCerimonialSerializer,
)


def _is_cerimonialista(user):
    return user.groups.filter(name__iexact="Cerimonialista").exists()


def _is_organizador(user):
    return user.groups.filter(name__iexact="Organizador do Evento").exists()


def _is_recepcao(user):
    return user.groups.filter(name__iexact="Recepção").exists()


def _is_participante_evento(user, evento):
    if user.is_staff:
        return True
    return (
        evento.cerimonialistas.filter(id=user.id).exists()
        or evento.organizadores.filter(id=user.id).exists()
        or evento.funcionarios.filter(id=user.id).exists()
    )


def _pode_editar_evento(user, evento):
    if user.is_staff:
        return True
    return _is_cerimonialista(user) and evento.cerimonialistas.filter(
        id=user.id
    ).exists()


def _salvar_imagem_db(evento, request):
    arquivo = request.FILES.get("imagem")
    if arquivo:
        evento.imagem_db_data = arquivo.read()
        evento.imagem_db_content_type = arquivo.content_type
        evento.imagem_db_filename = arquivo.name
        evento.save(
            update_fields=[
                "imagem_db_data",
                "imagem_db_content_type",
                "imagem_db_filename",
            ]
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_list_view(request):
    try:
        user = request.user
        eventos = EventoCerimonial.objects.prefetch_related(
            "cerimonialistas", "organizadores", "funcionarios"
        ).all()

        if not user.is_staff:
            eventos = eventos.filter(
                Q(cerimonialistas=user)
                | Q(organizadores=user)
                | Q(funcionarios=user)
            ).distinct()

        search = request.GET.get("search", "").strip()
        if search:
            eventos = eventos.filter(
                Q(nome__icontains=search)
                | Q(cep__icontains=search)
                | Q(numero__icontains=search)
                | Q(complemento__icontains=search)
            )

        confirmado = request.GET.get("confirmado")
        if confirmado is not None:
            confirmado_bool = str(confirmado).strip().lower() in {
                "1",
                "true",
                "yes",
            }
            eventos = eventos.filter(evento_confirmado=confirmado_bool)

        eventos = eventos.order_by("datetime_inicio")

        page = int(request.GET.get("page", 1))
        paginator = Paginator(eventos, 10)
        page_obj = paginator.get_page(page)

        serializer = EventoCerimonialListSerializer(
            page_obj.object_list, many=True, context={"request": request}
        )
        return Response(
            {
                "results": serializer.data,
                "count": paginator.count,
                "num_pages": paginator.num_pages,
                "current_page": page_obj.number,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            }
        )
    except Exception as exc:
        return Response(
            {"error": f"Erro ao listar eventos do cerimonial: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_create_view(request):
    user = request.user
    if not _is_cerimonialista(user) and not user.is_staff:
        return Response(
            {"error": "Apenas cerimonialistas podem criar eventos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = EventoCerimonialSerializer(
        data=request.data, context={"request": request}
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    evento = serializer.save(created_by=user)

    if not evento.cerimonialistas.filter(id=user.id).exists():
        evento.cerimonialistas.add(user)

    _salvar_imagem_db(evento, request)

    ListaConvidadosCerimonial.objects.get_or_create(
        evento=evento,
        defaults={
            "titulo": f"Lista de Convidados - {evento.nome}",
            "data_evento": (
                evento.datetime_inicio.date()
                if evento.datetime_inicio
                else None
            ),
            "ativa": True,
        },
    )

    return Response(
        EventoCerimonialSerializer(evento, context={"request": request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_detail_view(request, pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related(
            "cerimonialistas", "organizadores", "funcionarios"
        ).get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento do cerimonial não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _is_participante_evento(request.user, evento):
        return Response(
            {"error": "Sem permissão para acessar este evento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = EventoCerimonialSerializer(evento, context={"request": request})
    return Response(serializer.data)


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_update_view(request, pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related("cerimonialistas").get(
            pk=pk
        )
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento do cerimonial não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_editar_evento(request.user, evento):
        return Response(
            {"error": "Somente cerimonialistas podem editar este evento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = EventoCerimonialSerializer(
        evento,
        data=request.data,
        partial=(request.method == "PATCH"),
        context={"request": request},
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    evento = serializer.save(updated_by=request.user)
    _salvar_imagem_db(evento, request)

    return Response(
        EventoCerimonialSerializer(evento, context={"request": request}).data
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_delete_view(request, pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related("cerimonialistas").get(
            pk=pk
        )
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento do cerimonial não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_editar_evento(request.user, evento):
        return Response(
            {"error": "Somente cerimonialistas podem excluir este evento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    evento.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evento_cerimonial_imagem_db_view(request, pk):
    try:
        evento = EventoCerimonial.objects.prefetch_related(
            "cerimonialistas", "organizadores", "funcionarios"
        ).get(pk=pk)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento do cerimonial não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _is_participante_evento(request.user, evento):
        return Response(
            {"error": "Sem permissão para acessar imagem deste evento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not evento.imagem_db_data:
        return Response(
            {"error": "Imagem não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return HttpResponse(
        evento.imagem_db_data,
        content_type=evento.imagem_db_content_type or "application/octet-stream",
    )


__all__ = [
    "evento_cerimonial_list_view",
    "evento_cerimonial_create_view",
    "evento_cerimonial_detail_view",
    "evento_cerimonial_update_view",
    "evento_cerimonial_delete_view",
    "evento_cerimonial_imagem_db_view",
    "_is_cerimonialista",
    "_is_organizador",
    "_is_recepcao",
    "_is_participante_evento",
]
