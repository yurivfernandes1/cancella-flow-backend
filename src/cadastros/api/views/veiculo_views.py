from django.core.paginator import Paginator
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Veiculo
from ..serializers import VeiculoListSerializer, VeiculoSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def veiculo_list_view(request):
    """
    Lista veículos com paginação e busca.
    - Moradores: veem apenas seus próprios veículos
    - Portaria: vê todos os veículos do condomínio (read-only)
    - Síndicos e Admin: veem todos os veículos do condomínio
    """
    try:
        user = request.user

        # Busca
        search = request.GET.get("search", "")
        veiculos = Veiculo.objects.select_related("morador").all()

        # Controle de acesso por grupo
        is_sindico = user.groups.filter(name="Síndicos").exists()
        is_portaria = user.groups.filter(name="Portaria").exists()
        is_morador = user.groups.filter(name="Moradores").exists()

        # Filtrar por condomínio do morador (para todos os perfis exceto staff)
        if not user.is_staff and getattr(user, "condominio_id", None):
            veiculos = veiculos.filter(
                morador__condominio_id=user.condominio_id
            )

        if is_morador and not (user.is_staff or is_sindico or is_portaria):
            # Moradores veem apenas seus próprios veículos
            veiculos = veiculos.filter(morador=user)
        elif not (user.is_staff or is_sindico or is_portaria):
            # Usuários sem permissão não veem nada
            veiculos = Veiculo.objects.none()

        if search:
            veiculos = veiculos.filter(
                Q(placa__icontains=search)
                | Q(marca_modelo__icontains=search)
                | Q(morador__first_name__icontains=search)
                | Q(morador__last_name__icontains=search)
            )

        # Filtro de status
        is_active = request.GET.get("is_active", None)
        if is_active is not None:
            veiculos = veiculos.filter(is_active=is_active.lower() == "true")

        # Ordenação
        veiculos = veiculos.order_by("-created_on")

        # Paginação
        page = int(request.GET.get("page", 1))
        paginator = Paginator(veiculos, 10)
        page_obj = paginator.get_page(page)

        serializer = VeiculoListSerializer(page_obj.object_list, many=True)

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
            {"error": f"Erro ao listar veículos: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def veiculo_create_view(request):
    """
    Cria um novo veículo.
    Apenas Moradores, Síndicos e Administradores podem criar.
    Portaria não pode criar.
    """
    try:
        user = request.user
        is_sindico = user.groups.filter(name="Síndicos").exists()
        is_morador = user.groups.filter(name="Moradores").exists()
        is_portaria = user.groups.filter(name="Portaria").exists()

        if is_portaria and not (user.is_staff or is_sindico):
            return Response(
                {"error": "Portaria não pode cadastrar veículos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = VeiculoSerializer(data=request.data)
        if serializer.is_valid():
            # Se o usuário é morador e não forneceu morador_id, usar ele mesmo
            if is_morador and not request.data.get("morador_id"):
                veiculo = serializer.save(morador=user, created_by=user)
            else:
                veiculo = serializer.save(created_by=user)

            return Response(
                VeiculoSerializer(veiculo).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {"error": f"Erro ao criar veículo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def veiculo_detail_view(request, pk):
    """Obtém detalhes de um veículo específico"""
    try:
        veiculo = Veiculo.objects.select_related("morador").get(pk=pk)

        # Verificar permissão
        user = request.user
        is_sindico = user.groups.filter(name="Síndicos").exists()
        is_portaria = user.groups.filter(name="Portaria").exists()

        if not (
            user.is_staff
            or is_sindico
            or is_portaria
            or veiculo.morador == user
        ):
            return Response(
                {"error": "Você não tem permissão para ver este veículo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = VeiculoSerializer(veiculo)
        return Response(serializer.data)

    except Veiculo.DoesNotExist:
        return Response(
            {"error": "Veículo não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao obter veículo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def veiculo_update_view(request, pk):
    """
    Atualiza um veículo.
    Moradores podem editar apenas seus próprios veículos.
    Síndicos e Admin podem editar qualquer veículo.
    Portaria não pode editar.
    """
    try:
        user = request.user
        is_sindico = user.groups.filter(name="Síndicos").exists()
        is_portaria = user.groups.filter(name="Portaria").exists()

        if is_portaria and not (user.is_staff or is_sindico):
            return Response(
                {"error": "Portaria não pode editar veículos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        veiculo = Veiculo.objects.get(pk=pk)

        # Verificar se o usuário pode editar este veículo
        if not (user.is_staff or is_sindico or veiculo.morador == user):
            return Response(
                {"error": "Você não tem permissão para editar este veículo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = VeiculoSerializer(
            veiculo, data=request.data, partial=(request.method == "PATCH")
        )

        if serializer.is_valid():
            veiculo = serializer.save(updated_by=user)
            return Response(VeiculoSerializer(veiculo).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Veiculo.DoesNotExist:
        return Response(
            {"error": "Veículo não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao atualizar veículo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def veiculo_delete_view(request, pk):
    """
    Exclui um veículo permanentemente.
    Moradores podem excluir apenas seus próprios veículos.
    Síndicos e Admin podem excluir qualquer veículo.
    Portaria não pode excluir.
    """
    try:
        user = request.user
        is_sindico = user.groups.filter(name="Síndicos").exists()
        is_portaria = user.groups.filter(name="Portaria").exists()

        if is_portaria and not (user.is_staff or is_sindico):
            return Response(
                {"error": "Portaria não pode excluir veículos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        veiculo = Veiculo.objects.get(pk=pk)

        # Verificar se o usuário pode excluir este veículo
        if not (user.is_staff or is_sindico or veiculo.morador == user):
            return Response(
                {"error": "Você não tem permissão para excluir este veículo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        veiculo.delete()

        return Response(
            {"message": "Veículo excluído com sucesso."},
            status=status.HTTP_204_NO_CONTENT,
        )

    except Veiculo.DoesNotExist:
        return Response(
            {"error": "Veículo não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao excluir veículo: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
