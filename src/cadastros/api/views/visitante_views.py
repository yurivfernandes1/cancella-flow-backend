from django.core.paginator import Paginator
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Visitante
from ..serializers import VisitanteListSerializer, VisitanteSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def visitante_list_view(request):
    """
    Lista todos os visitantes com paginação e busca.
    - Portaria: vê todos os visitantes
    - Moradores: veem apenas seus próprios visitantes
    """
    try:
        user = request.user

        # Busca
        search = request.GET.get("search", "")
        visitantes = Visitante.objects.select_related("morador").all()

        # Controle de acesso por grupo
        is_portaria = user.groups.filter(name="Portaria").exists()
        is_morador = user.groups.filter(name="Moradores").exists()

        # Filtrar por condomínio do morador para Portaria (exceto staff)
        if (
            is_portaria
            and not user.is_staff
            and getattr(user, "condominio_id", None)
        ):
            visitantes = visitantes.filter(
                morador__condominio_id=user.condominio_id
            )
        elif is_morador and not (user.is_staff or is_portaria):
            # Moradores veem apenas seus próprios visitantes
            visitantes = visitantes.filter(morador=user)
        elif not (user.is_staff or is_portaria):
            # Usuários sem permissão não veem nada
            visitantes = Visitante.objects.none()

        if search:
            visitantes = visitantes.filter(
                Q(nome__icontains=search)
                | Q(documento__icontains=search)
                | Q(morador__first_name__icontains=search)
                | Q(morador__last_name__icontains=search)
            )

        # Ordenação
        visitantes = visitantes.order_by("-data_entrada")

        # Paginação
        page = int(request.GET.get("page", 1))
        paginator = Paginator(visitantes, 10)
        page_obj = paginator.get_page(page)

        serializer = VisitanteListSerializer(page_obj.object_list, many=True)

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
            {"error": f"Erro ao listar visitantes: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def visitante_create_view(request):
    """
    Cria um novo visitante.
    Moradores podem cadastrar visitantes para si mesmos.
    """
    try:
        user = request.user
        is_morador = user.groups.filter(name="Moradores").exists()

        if not (user.is_staff or is_morador):
            return Response(
                {"error": "Apenas Moradores podem cadastrar visitantes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Se for morador (e não admin), forçar morador_id para o próprio usuário
        data = request.data.copy()
        if is_morador and not user.is_staff:
            data["morador_id"] = user.id

        serializer = VisitanteSerializer(data=data)
        if serializer.is_valid():
            visitante = serializer.save()
            return Response(
                VisitanteSerializer(visitante).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {"error": f"Erro ao criar visitante: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def visitante_detail_view(request, pk):
    """
    Obtém detalhes de um visitante específico
    """
    try:
        visitante = Visitante.objects.select_related("morador").get(pk=pk)
        user = request.user
        is_portaria = user.groups.filter(name="Portaria").exists()
        is_morador = user.groups.filter(name="Moradores").exists()
        if (
            is_morador
            and not (user.is_staff or is_portaria)
            and visitante.morador != user
        ):
            return Response(
                {"error": "Você não tem permissão para ver este visitante."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = VisitanteSerializer(visitante)
        return Response(serializer.data)

    except Visitante.DoesNotExist:
        return Response(
            {"error": "Visitante não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao obter visitante: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def visitante_update_view(request, pk):
    """
    Atualiza um visitante.
    - Portaria: pode editar data_entrada de qualquer visitante
    - Moradores: podem editar seus próprios visitantes
    """
    try:
        user = request.user
        is_portaria = user.groups.filter(name="Portaria").exists()
        is_morador = user.groups.filter(name="Moradores").exists()

        visitante = Visitante.objects.get(pk=pk)

        # Verificar permissões
        if is_portaria or user.is_staff:
            # Portaria e Admin podem editar qualquer visitante
            pass
        elif is_morador:
            # Moradores só podem editar seus próprios visitantes
            if visitante.morador != user:
                return Response(
                    {"error": "Você só pode editar seus próprios visitantes."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            return Response(
                {"error": "Você não tem permissão para editar visitantes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = VisitanteSerializer(
            visitante, data=request.data, partial=(request.method == "PATCH")
        )

        if serializer.is_valid():
            visitante = serializer.save()
            return Response(VisitanteSerializer(visitante).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Visitante.DoesNotExist:
        return Response(
            {"error": "Visitante não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao atualizar visitante: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def visitante_delete_view(request, pk):
    """
    Exclui um visitante.
    Moradores podem excluir seus próprios visitantes.
    """
    try:
        user = request.user
        is_morador = user.groups.filter(name="Moradores").exists()

        visitante = Visitante.objects.get(pk=pk)

        # Verificar permissões
        if user.is_staff:
            # Admin pode excluir qualquer visitante
            pass
        elif is_morador and visitante.morador == user:
            # Morador pode excluir seu próprio visitante
            pass
        else:
            return Response(
                {"error": "Você só pode excluir seus próprios visitantes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        visitante = Visitante.objects.get(pk=pk)
        visitante.delete()

        return Response(
            {"message": "Visitante excluído com sucesso."},
            status=status.HTTP_204_NO_CONTENT,
        )

    except Visitante.DoesNotExist:
        return Response(
            {"error": "Visitante não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao excluir visitante: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
