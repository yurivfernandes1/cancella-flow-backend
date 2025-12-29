from django.core.paginator import Paginator
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Unidade
from ..serializers import (
    UnidadeCreateBulkSerializer,
    UnidadeListSerializer,
    UnidadeSerializer,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unidade_list_view(request):
    """
    Lista todas as unidades com paginação e busca.
    - Síndicos e Admin: veem todas as unidades do condomínio
    - Portaria: vê todas as unidades do condomínio
    - Moradores: veem apenas suas próprias unidades
    """
    try:
        user = request.user

        # Busca
        search = request.GET.get("search", "")
        # Relação com usuários é reversa (User.unidade related_name='morador'),
        # portanto devemos usar prefetch_related em vez de select_related
        unidades = Unidade.objects.prefetch_related("morador").all()

        # Controle de acesso por grupo
        is_sindico = user.groups.filter(name="Síndicos").exists()
        is_portaria = user.groups.filter(name="Portaria").exists()
        is_morador = user.groups.filter(name="Moradores").exists()

        # Filtrar por condomínio do usuário (considerando unidades sem morador)
        if hasattr(user, "condominio_id") and user.condominio_id:
            unidades = unidades.filter(
                Q(morador__condominio_id=user.condominio_id)
                | Q(created_by__condominio_id=user.condominio_id)
            ).distinct()

        if is_morador and not (user.is_staff or is_sindico or is_portaria):
            # Moradores veem apenas suas próprias unidades
            unidades = unidades.filter(morador=user)
        elif not (user.is_staff or is_sindico or is_portaria):
            # Usuários sem permissão não veem nada
            unidades = Unidade.objects.none()

        if search:
            unidades = unidades.filter(
                Q(numero__icontains=search)
                | Q(bloco__icontains=search)
                | Q(morador__first_name__icontains=search)
                | Q(morador__last_name__icontains=search)
            ).distinct()

        # Filtro de status
        is_active = request.GET.get("is_active", None)
        if is_active is not None:
            unidades = unidades.filter(is_active=is_active.lower() == "true")

        # Ordenação
        unidades = unidades.order_by("bloco", "numero")

        # Paginação
        page = int(request.GET.get("page", 1))
        paginator = Paginator(unidades, 10)
        page_obj = paginator.get_page(page)

        serializer = UnidadeListSerializer(page_obj.object_list, many=True)

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
            {"error": f"Erro ao listar unidades: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unidade_create_view(request):
    """
    Cria uma nova unidade.
    Apenas Síndicos e Administradores podem criar.
    """
    try:
        user = request.user
        is_sindico = user.groups.filter(name="Síndicos").exists()

        if not (user.is_staff or is_sindico):
            return Response(
                {"error": "Apenas Síndicos podem cadastrar unidades."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UnidadeSerializer(data=request.data)
        if serializer.is_valid():
            unidade = serializer.save(created_by=user)
            return Response(
                UnidadeSerializer(unidade).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {"error": f"Erro ao criar unidade: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unidade_create_bulk_view(request):
    """
    Cria múltiplas unidades de uma vez.
    Apenas Síndicos e Administradores podem criar.
    """
    try:
        user = request.user
        is_sindico = user.groups.filter(name="Síndicos").exists()

        if not (user.is_staff or is_sindico):
            return Response(
                {"error": "Apenas Síndicos podem cadastrar unidades."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UnidadeCreateBulkSerializer(data=request.data)
        if serializer.is_valid():
            unidades = serializer.save()

            # Atualizar created_by de todas as unidades criadas
            for unidade in unidades:
                unidade.created_by = user
                unidade.save()

            return Response(
                {
                    "message": f"{len(unidades)} unidades criadas com sucesso.",
                    "unidades": UnidadeListSerializer(
                        unidades, many=True
                    ).data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {"error": f"Erro ao criar unidades: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unidade_detail_view(request, pk):
    """
    Obtém detalhes de uma unidade específica
    """
    try:
        # Relação reversa: usar prefetch_related
        unidade = Unidade.objects.prefetch_related("morador").get(pk=pk)
        serializer = UnidadeSerializer(unidade)
        return Response(serializer.data)

    except Unidade.DoesNotExist:
        return Response(
            {"error": "Unidade não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao obter unidade: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def unidade_update_view(request, pk):
    """
    Atualiza uma unidade.
    Apenas Síndicos e Administradores podem editar.
    """
    try:
        user = request.user
        is_sindico = user.groups.filter(name="Síndicos").exists()

        if not (user.is_staff or is_sindico):
            return Response(
                {"error": "Apenas Síndicos podem editar unidades."},
                status=status.HTTP_403_FORBIDDEN,
            )

        unidade = Unidade.objects.get(pk=pk)
        serializer = UnidadeSerializer(
            unidade, data=request.data, partial=(request.method == "PATCH")
        )

        if serializer.is_valid():
            unidade = serializer.save(updated_by=user)
            return Response(UnidadeSerializer(unidade).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Unidade.DoesNotExist:
        return Response(
            {"error": "Unidade não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao atualizar unidade: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def unidade_inactivate_view(request, pk):
    """
    Inativa uma unidade (soft delete).
    Apenas Síndicos e Administradores podem inativar.
    """
    try:
        user = request.user
        is_sindico = user.groups.filter(name="Síndicos").exists()

        if not (user.is_staff or is_sindico):
            return Response(
                {"error": "Apenas Síndicos podem inativar unidades."},
                status=status.HTTP_403_FORBIDDEN,
            )

        unidade = Unidade.objects.get(pk=pk)
        unidade.is_active = False
        unidade.updated_by = user
        unidade.save()

        return Response(
            {
                "message": "Unidade inativada com sucesso.",
                "unidade": UnidadeSerializer(unidade).data,
            }
        )

    except Unidade.DoesNotExist:
        return Response(
            {"error": "Unidade não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao inativar unidade: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def unidade_delete_view(request, pk):
    """
    Exclui uma unidade permanentemente.
    Apenas Administradores podem excluir.
    """
    try:
        user = request.user

        if not user.is_staff:
            return Response(
                {"error": "Apenas administradores podem excluir unidades."},
                status=status.HTTP_403_FORBIDDEN,
            )

        unidade = Unidade.objects.get(pk=pk)
        unidade.delete()

        return Response(
            {"message": "Unidade excluída com sucesso."},
            status=status.HTTP_204_NO_CONTENT,
        )

    except Unidade.DoesNotExist:
        return Response(
            {"error": "Unidade não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao excluir unidade: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
