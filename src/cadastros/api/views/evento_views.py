from access.api.permissions import IsStaffOrSindico
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Evento
from ..serializers.evento_serializer import (
    EventoListSerializer,
    EventoSerializer,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evento_list_view(request):
    """
    Lista eventos com filtros baseados no perfil do usuário:
    - Síndicos: veem todos os eventos (passados, atuais e futuros)
    - Moradores: veem apenas eventos futuros (hoje em diante)
    - Portaria: veem eventos de hoje e amanhã
    """
    try:
        user = request.user
        now_dt = timezone.now()

        eventos = Evento.objects.select_related("espaco", "created_by").all()

        # Controle de acesso por grupo
        is_sindico = user.groups.filter(
            Q(name__iexact="Síndicos") | Q(name__iexact="Sindicos")
        ).exists()
        is_portaria = user.groups.filter(name="Portaria").exists()
        is_morador = user.groups.filter(name="Moradores").exists()

        # Escopo por condomínio para todos os perfis não-staff
        if not user.is_staff and getattr(user, "condominio_id", None):
            eventos = eventos.filter(
                created_by__condominio_id=user.condominio_id
            )

        # Filtrar por perfil
        if is_sindico or user.is_staff:
            # Síndicos veem todos
            pass
        elif is_portaria:
            # Portaria vê eventos de hoje e amanhã
            hoje_inicio = now_dt.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            amanha_fim = hoje_inicio + timezone.timedelta(days=2)
            eventos = eventos.filter(
                datetime_inicio__lt=amanha_fim, datetime_fim__gte=hoje_inicio
            )
        elif is_morador:
            # Moradores veem eventos futuros (a partir de agora)
            eventos = eventos.filter(datetime_inicio__gte=now_dt)
        else:
            # Sem permissão
            eventos = Evento.objects.none()

        # Busca
        search = request.GET.get("search", "")
        if search:
            eventos = eventos.filter(
                Q(titulo__icontains=search)
                | Q(descricao__icontains=search)
                | Q(local_texto__icontains=search)
                | Q(espaco__nome__icontains=search)
            )

        # Ordenação
        eventos = eventos.order_by("datetime_inicio")

        # Paginação
        page = int(request.GET.get("page", 1))
        paginator = Paginator(eventos, 10)
        page_obj = paginator.get_page(page)

        serializer = EventoListSerializer(
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

    except Exception as e:
        return Response(
            {"error": f"Erro ao listar eventos: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffOrSindico])
def evento_create_view(request):
    """
    Cria um novo evento.
    Apenas Síndicos podem criar eventos.
    """
    try:
        serializer = EventoSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            evento = serializer.save(created_by=request.user)
            return Response(
                EventoSerializer(evento, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {"error": f"Erro ao criar evento: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evento_detail_view(request, pk):
    """
    Obtém detalhes de um evento específico.
    """
    try:
        evento = Evento.objects.select_related("espaco", "created_by").get(
            pk=pk
        )
        user = request.user
        if not user.is_staff and getattr(user, "condominio_id", None):
            creator_condo = getattr(
                getattr(evento, "created_by", None), "condominio_id", None
            )
            if creator_condo != getattr(user, "condominio_id", None):
                return Response(
                    {"error": "Acesso negado a este evento."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        serializer = EventoSerializer(evento, context={"request": request})
        return Response(serializer.data)

    except Evento.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao obter evento: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsStaffOrSindico])
def evento_update_view(request, pk):
    """
    Atualiza um evento.
    Apenas Síndicos podem editar eventos.
    """
    try:
        evento = Evento.objects.select_related("created_by").get(pk=pk)
        user = request.user
        if not user.is_staff and getattr(user, "condominio_id", None):
            creator_condo = getattr(
                getattr(evento, "created_by", None), "condominio_id", None
            )
            if creator_condo != getattr(user, "condominio_id", None):
                return Response(
                    {
                        "error": "Apenas Síndicos do mesmo condomínio podem editar."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        serializer = EventoSerializer(
            evento,
            data=request.data,
            partial=(request.method == "PATCH"),
            context={"request": request},
        )

        if serializer.is_valid():
            evento = serializer.save(updated_by=request.user)
            return Response(
                EventoSerializer(evento, context={"request": request}).data
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Evento.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao atualizar evento: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsStaffOrSindico])
def evento_delete_view(request, pk):
    """
    Exclui um evento.
    Apenas Síndicos podem excluir eventos.
    """
    try:
        evento = Evento.objects.select_related("created_by").get(pk=pk)
        user = request.user
        if not user.is_staff and getattr(user, "condominio_id", None):
            creator_condo = getattr(
                getattr(evento, "created_by", None), "condominio_id", None
            )
            if creator_condo != getattr(user, "condominio_id", None):
                return Response(
                    {
                        "error": "Apenas Síndicos do mesmo condomínio podem excluir."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        evento.delete()

        return Response(
            {"message": "Evento excluído com sucesso."},
            status=status.HTTP_204_NO_CONTENT,
        )

    except Evento.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao excluir evento: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
