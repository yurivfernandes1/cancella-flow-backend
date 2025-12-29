from django.core.paginator import Paginator
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Espaco, EspacoInventarioItem, EspacoReserva
from ..serializers import (
    EspacoInventarioItemListSerializer,
    EspacoInventarioItemSerializer,
    EspacoListSerializer,
    EspacoReservaListSerializer,
    EspacoReservaSerializer,
    EspacoSerializer,
)


def _is_sindico(user):
    return user.groups.filter(
        Q(name__iexact="Síndicos") | Q(name__iexact="Sindicos")
    ).exists()


# ------------------------ Espaços ------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def espaco_list_view(request):
    """
    Lista espaços com filtros e paginação.
    Visualizam: Síndico, Portaria, Moradores.
    """
    try:
        user = request.user

        # Controle de acesso: negar outros perfis
        if not (
            user.is_staff
            or _is_sindico(user)
            or user.groups.filter(name__iexact="Portaria").exists()
            or user.groups.filter(name__iexact="Moradores").exists()
        ):
            return Response([], status=status.HTTP_200_OK)

        search = request.GET.get("search", "").strip()
        espacos = Espaco.objects.all()

        # Filtrar por condomínio do criador (exceto staff)
        if not user.is_staff and getattr(user, "condominio_id", None):
            espacos = espacos.filter(
                created_by__condominio_id=user.condominio_id
            )

        if search:
            espacos = espacos.filter(Q(nome__icontains=search))

        is_active = request.GET.get("is_active")
        if is_active is not None:
            espacos = espacos.filter(
                is_active=is_active.lower() in {"1", "true", "True"}
            )

        espacos = espacos.order_by("nome")

        page = int(request.GET.get("page", 1))
        paginator = Paginator(espacos, 10)
        page_obj = paginator.get_page(page)

        serializer = EspacoListSerializer(page_obj.object_list, many=True)
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
            {"error": f"Erro ao listar espaços: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def espaco_create_view(request):
    """Apenas Síndico pode criar/editar/excluir."""
    try:
        user = request.user
        if not _is_sindico(user):
            return Response(
                {"error": "Apenas Síndicos podem criar espaços."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = EspacoSerializer(data=request.data)
        if serializer.is_valid():
            espaco = serializer.save(created_by=user)
            return Response(
                EspacoSerializer(espaco).data, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {"error": f"Erro ao criar espaço: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def espaco_detail_view(request, pk):
    try:
        espaco = Espaco.objects.get(pk=pk)
        user = request.user
        if not user.is_staff and getattr(user, "condominio_id", None):
            creator_condo = getattr(
                getattr(espaco, "created_by", None), "condominio_id", None
            )
            if creator_condo != getattr(user, "condominio_id", None):
                return Response(
                    {"error": "Acesso negado a este espaço."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return Response(EspacoSerializer(espaco).data)
    except Espaco.DoesNotExist:
        return Response(
            {"error": "Espaço não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao obter espaço: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def espaco_update_view(request, pk):
    try:
        user = request.user
        if not _is_sindico(user):
            return Response(
                {"error": "Apenas Síndicos podem editar espaços."},
                status=status.HTTP_403_FORBIDDEN,
            )
        espaco = Espaco.objects.get(pk=pk)
        if not user.is_staff and getattr(user, "condominio_id", None):
            creator_condo = getattr(
                getattr(espaco, "created_by", None), "condominio_id", None
            )
            if creator_condo != getattr(user, "condominio_id", None):
                return Response(
                    {
                        "error": "Apenas Síndicos do mesmo condomínio podem editar."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        serializer = EspacoSerializer(
            espaco, data=request.data, partial=(request.method == "PATCH")
        )
        if serializer.is_valid():
            espaco = serializer.save(updated_by=user)
            return Response(EspacoSerializer(espaco).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Espaco.DoesNotExist:
        return Response(
            {"error": "Espaço não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao atualizar espaço: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def espaco_delete_view(request, pk):
    try:
        user = request.user
        if not _is_sindico(user):
            return Response(
                {"error": "Apenas Síndicos podem excluir espaços."},
                status=status.HTTP_403_FORBIDDEN,
            )
        espaco = Espaco.objects.get(pk=pk)
        if not user.is_staff and getattr(user, "condominio_id", None):
            creator_condo = getattr(
                getattr(espaco, "created_by", None), "condominio_id", None
            )
            if creator_condo != getattr(user, "condominio_id", None):
                return Response(
                    {
                        "error": "Apenas Síndicos do mesmo condomínio podem excluir."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        espaco.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except Espaco.DoesNotExist:
        return Response(
            {"error": "Espaço não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao excluir espaço: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ------------------------ Inventário ------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def espaco_inventario_list_view(request):
    """Lista itens do inventário. Visualizam: Síndico, Portaria e Moradores."""
    try:
        user = request.user
        if not (
            user.is_staff
            or _is_sindico(user)
            or user.groups.filter(name__iexact="Portaria").exists()
            or user.groups.filter(name__iexact="Moradores").exists()
        ):
            return Response([], status=status.HTTP_200_OK)

        search = request.GET.get("search", "").strip()
        espaco_id = request.GET.get("espaco_id")
        itens = EspacoInventarioItem.objects.select_related("espaco").all()

        # Filtrar por condomínio do criador (item ou espaço) para perfis não-staff
        if not user.is_staff and getattr(user, "condominio_id", None):
            itens = itens.filter(
                Q(created_by__condominio_id=user.condominio_id)
                | Q(espaco__created_by__condominio_id=user.condominio_id)
            )

        if espaco_id:
            itens = itens.filter(espaco_id=espaco_id)
        if search:
            itens = itens.filter(
                Q(nome__icontains=search)
                | Q(codigo__icontains=search)
                | Q(espaco__nome__icontains=search)
            )

        is_active = request.GET.get("is_active")
        if is_active is not None:
            itens = itens.filter(
                is_active=is_active.lower() in {"1", "true", "True"}
            )

        itens = itens.order_by("espaco__nome", "nome")

        # Paginação: por padrão, 5 por página (pode sobrescrever com ?page_size=N até 50)
        page = int(request.GET.get("page", 1))
        try:
            per_page = int(request.GET.get("page_size", 5))
        except (TypeError, ValueError):
            per_page = 5
        per_page = max(1, min(per_page, 50))
        paginator = Paginator(itens, per_page)
        page_obj = paginator.get_page(page)

        serializer = EspacoInventarioItemListSerializer(
            page_obj.object_list, many=True
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
            {"error": f"Erro ao listar inventário: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def espaco_inventario_create_view(request):
    try:
        user = request.user
        if not _is_sindico(user):
            return Response(
                {"error": "Apenas Síndicos podem criar itens de inventário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = EspacoInventarioItemSerializer(data=request.data)
        if serializer.is_valid():
            item = serializer.save(created_by=user)
            return Response(
                EspacoInventarioItemSerializer(item).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {"error": f"Erro ao criar item de inventário: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def espaco_inventario_detail_view(request, pk):
    try:
        item = EspacoInventarioItem.objects.select_related("espaco").get(pk=pk)
        user = request.user
        if not user.is_staff and getattr(user, "condominio_id", None):
            item_creator_condo = getattr(
                getattr(item, "created_by", None), "condominio_id", None
            )
            espaco_creator_condo = getattr(
                getattr(getattr(item, "espaco", None), "created_by", None),
                "condominio_id",
                None,
            )
            same_cond = item_creator_condo == getattr(
                user, "condominio_id", None
            ) or espaco_creator_condo == getattr(user, "condominio_id", None)
            if not same_cond:
                return Response(
                    {"error": "Acesso negado a este item."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return Response(EspacoInventarioItemSerializer(item).data)
    except EspacoInventarioItem.DoesNotExist:
        return Response(
            {"error": "Item de inventário não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao obter item de inventário: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def espaco_inventario_update_view(request, pk):
    try:
        user = request.user
        if not _is_sindico(user):
            return Response(
                {"error": "Apenas Síndicos podem editar itens de inventário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        item = EspacoInventarioItem.objects.get(pk=pk)
        if not user.is_staff and getattr(user, "condominio_id", None):
            item_creator_condo = getattr(
                getattr(item, "created_by", None), "condominio_id", None
            )
            espaco_creator_condo = getattr(
                getattr(getattr(item, "espaco", None), "created_by", None),
                "condominio_id",
                None,
            )
            same_cond = item_creator_condo == getattr(
                user, "condominio_id", None
            ) or espaco_creator_condo == getattr(user, "condominio_id", None)
            if not same_cond:
                return Response(
                    {
                        "error": "Apenas Síndicos do mesmo condomínio podem editar."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        serializer = EspacoInventarioItemSerializer(
            item, data=request.data, partial=(request.method == "PATCH")
        )
        if serializer.is_valid():
            item = serializer.save(updated_by=user)
            return Response(EspacoInventarioItemSerializer(item).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except EspacoInventarioItem.DoesNotExist:
        return Response(
            {"error": "Item de inventário não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao atualizar item de inventário: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def espaco_inventario_delete_view(request, pk):
    try:
        user = request.user
        if not _is_sindico(user):
            return Response(
                {
                    "error": "Apenas Síndicos podem excluir itens de inventário."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        item = EspacoInventarioItem.objects.get(pk=pk)
        if not user.is_staff and getattr(user, "condominio_id", None):
            item_creator_condo = getattr(
                getattr(item, "created_by", None), "condominio_id", None
            )
            espaco_creator_condo = getattr(
                getattr(getattr(item, "espaco", None), "created_by", None),
                "condominio_id",
                None,
            )
            same_cond = item_creator_condo == getattr(
                user, "condominio_id", None
            ) or espaco_creator_condo == getattr(user, "condominio_id", None)
            if not same_cond:
                return Response(
                    {
                        "error": "Apenas Síndicos do mesmo condomínio podem excluir."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except EspacoInventarioItem.DoesNotExist:
        return Response(
            {"error": "Item de inventário não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao excluir item de inventário: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ------------------------ Reservas ------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def espaco_reserva_list_view(request):
    """
    Lista reservas.
    Visualizam: Síndico, Portaria, Moradores. Morador vê somente as suas.
    """
    try:
        user = request.user
        is_sindico = _is_sindico(user)
        is_portaria = user.groups.filter(name__iexact="Portaria").exists()
        is_morador = user.groups.filter(name__iexact="Moradores").exists()

        if not (
            user.is_authenticated
            and (is_sindico or is_portaria or is_morador or user.is_staff)
        ):
            return Response([], status=status.HTTP_200_OK)

        reservas = EspacoReserva.objects.select_related(
            "espaco", "morador", "morador__unidade"
        ).all()

        # Filtrar por condomínio do contexto do registro para perfis não-staff
        # Considerar diferentes associações: criado por, espaço criado por ou unidade do morador
        if not user.is_staff and getattr(user, "condominio_id", None):
            reservas = reservas.filter(
                Q(created_by__condominio_id=user.condominio_id)
                | Q(espaco__created_by__condominio_id=user.condominio_id)
                # condominio associado diretamente ao usuário (morador)
                | Q(morador__condominio_id=user.condominio_id)
            )

        # Morador vê apenas as suas
        if is_morador and not (is_sindico or is_portaria or user.is_staff):
            reservas = reservas.filter(morador=user)

        espaco_id = request.GET.get("espaco_id")
        if espaco_id:
            reservas = reservas.filter(espaco_id=espaco_id)

        morador_id = request.GET.get("morador_id")
        if morador_id:
            reservas = reservas.filter(morador_id=morador_id)

        data_ini = request.GET.get("data_ini")
        data_fim = request.GET.get("data_fim")
        if data_ini:
            reservas = reservas.filter(data_reserva__gte=data_ini)
        if data_fim:
            reservas = reservas.filter(data_reserva__lte=data_fim)

        reservas = reservas.order_by("-data_reserva").distinct()

        page = int(request.GET.get("page", 1))
        paginator = Paginator(reservas, 10)
        page_obj = paginator.get_page(page)

        serializer = EspacoReservaListSerializer(
            page_obj.object_list, many=True
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
            {"error": f"Erro ao listar reservas: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def espaco_reserva_create_view(request):
    """
    Moradores podem criar suas próprias reservas; Síndicos também podem criar para qualquer morador.
    Validação: não permite reservas na mesma data para o mesmo espaço (já validado no model),
    e mostra se há outras reservas na mesma data para o condomínio.
    """
    try:
        user = request.user
        is_sindico = _is_sindico(user)
        is_morador = user.groups.filter(name__iexact="Moradores").exists()

        if not (is_sindico or is_morador or user.is_staff):
            return Response(
                {"error": "Apenas Moradores e Síndicos podem criar reservas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Passar o contexto com a request para o serializer
        serializer = EspacoReservaSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            reserva = serializer.save(created_by=user)

            # Se for morador, garantir que está criando para si próprio
            if is_morador and reserva.morador_id != user.id:
                reserva.delete()
                return Response(
                    {
                        "error": "Moradores só podem criar reservas para si mesmos."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            return Response(
                EspacoReservaSerializer(reserva).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {"error": f"Erro ao criar reserva: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def espaco_reserva_detail_view(request, pk):
    try:
        reserva = EspacoReserva.objects.select_related(
            "espaco", "morador"
        ).get(pk=pk)
        user = request.user
        if not user.is_staff and getattr(user, "condominio_id", None):
            reserva_creator_condo = getattr(
                getattr(reserva, "created_by", None), "condominio_id", None
            )
            if reserva_creator_condo != getattr(user, "condominio_id", None):
                return Response(
                    {"error": "Acesso negado a esta reserva."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return Response(EspacoReservaSerializer(reserva).data)
    except EspacoReserva.DoesNotExist:
        return Response(
            {"error": "Reserva não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao obter reserva: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def espaco_reserva_update_view(request, pk):
    """Somente Síndicos podem editar reservas (regras simplificadas)."""
    try:
        user = request.user
        if not _is_sindico(user):
            return Response(
                {"error": "Apenas Síndicos podem editar reservas."},
                status=status.HTTP_403_FORBIDDEN,
            )
        reserva = EspacoReserva.objects.select_related(
            "created_by", "espaco__created_by"
        ).get(pk=pk)
        # Síndico só pode editar reservas do seu condomínio (pelo criador)
        if not user.is_staff and getattr(user, "condominio_id", None):
            creator_condo = getattr(
                getattr(reserva, "created_by", None), "condominio_id", None
            )
            if creator_condo != getattr(user, "condominio_id", None):
                return Response(
                    {
                        "error": "Apenas Síndicos do mesmo condomínio podem editar."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        serializer = EspacoReservaSerializer(
            reserva,
            data=request.data,
            partial=(request.method == "PATCH"),
            context={"request": request},
        )
        if serializer.is_valid():
            reserva = serializer.save(updated_by=user)
            return Response(EspacoReservaSerializer(reserva).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except EspacoReserva.DoesNotExist:
        return Response(
            {"error": "Reserva não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao atualizar reserva: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def espaco_reserva_delete_view(request, pk):
    """Moradores podem cancelar suas próprias reservas; Síndicos podem excluir qualquer."""
    try:
        user = request.user
        is_sindico = _is_sindico(user)

        reserva = EspacoReserva.objects.select_related(
            "created_by", "espaco__created_by"
        ).get(pk=pk)

        # Morador só pode cancelar suas próprias reservas
        if not is_sindico:
            morador_id = getattr(reserva, "morador_id", None)
            if morador_id is None:
                morador_id = getattr(
                    getattr(reserva, "morador", None), "id", None
                )
            if morador_id != user.id:
                return Response(
                    {"error": "Você só pode cancelar suas próprias reservas."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            # Síndico só pode excluir reservas do seu condomínio
            if not user.is_staff and getattr(user, "condominio_id", None):
                creator_condo = getattr(
                    getattr(reserva, "created_by", None), "condominio_id", None
                )
                if creator_condo != getattr(user, "condominio_id", None):
                    return Response(
                        {
                            "error": "Apenas Síndicos do mesmo condomínio podem excluir."
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

        reserva.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except EspacoReserva.DoesNotExist:
        return Response(
            {"error": "Reserva não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao excluir reserva: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def espaco_reserva_hoje_view(request):
    """
    Lista reservas do dia atual (para portaria).
    Visualizam: Síndico, Portaria.
    """
    try:
        user = request.user
        is_sindico = _is_sindico(user)
        is_portaria = user.groups.filter(name__iexact="Portaria").exists()

        if not (user.is_staff or is_sindico or is_portaria):
            return Response(
                {"error": "Acesso negado."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from datetime import date

        hoje = date.today()

        reservas = EspacoReserva.objects.select_related(
            "espaco", "morador", "morador__unidade"
        ).filter(data_reserva=hoje, status="confirmada")

        # Filtrar por condomínio do contexto do registro para síndico/portaria (exceto staff)
        # Considerar criado por, espaço criado por ou unidade do morador
        if not user.is_staff and getattr(user, "condominio_id", None):
            reservas = reservas.filter(
                Q(created_by__condominio_id=user.condominio_id)
                | Q(espaco__created_by__condominio_id=user.condominio_id)
                | Q(morador__condominio_id=user.condominio_id)
            )

        reservas = reservas.order_by("espaco__nome").distinct()

        serializer = EspacoReservaListSerializer(reservas, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {"error": f"Erro ao listar reservas de hoje: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def espaco_disponibilidade_view(request):
    """
    Retorna as datas ocupadas de um espaço específico.
    Parâmetros: espaco_id (obrigatório), data_ini (opcional), data_fim (opcional).
    """
    try:
        espaco_id = request.GET.get("espaco_id")
        if not espaco_id:
            return Response(
                {"error": "Parâmetro espaco_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar se o espaço existe e pertence ao mesmo condomínio (via created_by)
        try:
            espaco = Espaco.objects.get(pk=espaco_id)
            user = request.user
            if not user.is_staff and getattr(user, "condominio_id", None):
                creator_condo = getattr(
                    getattr(espaco, "created_by", None), "condominio_id", None
                )
                if creator_condo != getattr(user, "condominio_id", None):
                    return Response(
                        {"error": "Acesso negado a este espaço."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
        except Espaco.DoesNotExist:
            return Response(
                {"error": "Espaço não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data_ini = request.GET.get("data_ini")
        data_fim = request.GET.get("data_fim")

        reservas = EspacoReserva.objects.filter(
            espaco_id=espaco_id, status="confirmada"
        )

        if data_ini:
            reservas = reservas.filter(data_reserva__gte=data_ini)
        if data_fim:
            reservas = reservas.filter(data_reserva__lte=data_fim)

        # Retornar lista de datas ocupadas em formato ISO
        datas_ocupadas = list(
            reservas.values_list("data_reserva", flat=True).distinct()
        )
        datas_ocupadas_str = [d.isoformat() for d in datas_ocupadas]

        return Response({"datas_ocupadas": datas_ocupadas_str})
    except Exception as e:
        return Response(
            {"error": f"Erro ao verificar disponibilidade: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
