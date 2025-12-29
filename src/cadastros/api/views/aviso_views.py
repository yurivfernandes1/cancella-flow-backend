from access.api.permissions import IsStaffOrSindico
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Aviso
from ..serializers import (
    AvisoListSerializer,
    AvisoOptionsSerializer,
    AvisoSerializer,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def aviso_list_view(request):
    """
    Lista avisos com filtros e paginação.
    - Usuários veem apenas avisos do(s) seu(s) grupo(s) e do seu condomínio (se aplicável)
    - Admin (staff que não é Síndico) não recebe avisos
    Suporta filtros: search, status, prioridade, grupo_id, vigente=1
    """
    try:
        user = request.user
        avisos = Aviso.objects.select_related("grupo", "created_by")
        # Define se é síndico pelo nome do grupo (aceita variação sem acento)
        is_sindico = user.groups.filter(
            Q(name__iexact="Síndicos") | Q(name__iexact="Sindicos")
        ).exists()

        # Admin que não é síndico não recebe avisos
        if user.is_staff and not is_sindico:
            avisos = Aviso.objects.none()
        else:
            # Síndico vê todos os avisos do próprio condomínio (pelo criador)
            if is_sindico and getattr(user, "condominio", None):
                avisos = avisos.filter(created_by__condominio=user.condominio)
            else:
                # Demais perfis: filtrar por grupo E por condomínio do criador
                grupos_ids = list(user.groups.values_list("id", flat=True))
                avisos = avisos.filter(grupo_id__in=grupos_ids)
                if getattr(user, "condominio", None):
                    avisos = avisos.filter(
                        created_by__condominio=user.condominio
                    )

                # Se for morador, filtrar avisos de encomenda apenas da sua unidade
                # Identificamos avisos de encomenda pelo título que contém "Nova encomenda"
                is_morador = user.groups.filter(name="Moradores").exists()
                if is_morador and getattr(user, "unidade", None):
                    # Mostrar avisos de encomenda apenas se houver encomendas pendentes (sem retirada) para a unidade
                    # Nota: o título do aviso contém a identificação da unidade
                    from ...models import Encomenda

                    has_pending = Encomenda.objects.filter(
                        unidade_id=user.unidade_id, retirado_em__isnull=True
                    ).exists()

                    if has_pending:
                        avisos = avisos.filter(
                            Q(titulo__icontains="Nova encomenda")
                            & Q(
                                titulo__icontains=user.unidade.identificacao_completa
                            )
                            | ~Q(titulo__icontains="Nova encomenda")
                        )
                    else:
                        avisos = avisos.filter(
                            ~Q(titulo__icontains="Nova encomenda")
                        )

        # Filtros
        search = request.GET.get("search", "").strip()
        if search:
            avisos = avisos.filter(
                Q(titulo__icontains=search)
                | Q(descricao__icontains=search)
                | Q(grupo__name__icontains=search)
            )

        status_filter = request.GET.get("status")
        if status_filter:
            avisos = avisos.filter(status=status_filter)

        prioridade_filter = request.GET.get("prioridade")
        if prioridade_filter:
            avisos = avisos.filter(prioridade=prioridade_filter)

        grupo_id = request.GET.get("grupo_id")
        if grupo_id:
            avisos = avisos.filter(grupo_id=grupo_id)

        vigente = request.GET.get("vigente")
        if vigente in {"1", "true", "True"}:
            from django.utils import timezone

            now = timezone.now()
            avisos = avisos.filter(
                status=Aviso.STATUS_ATIVO,
                data_inicio__lte=now,
            ).filter(Q(data_fim__gte=now) | Q(data_fim__isnull=True))

        # Ordenação
        avisos = avisos.order_by("-prioridade", "-data_inicio")

        # Paginação
        page = int(request.GET.get("page", 1))
        paginator = Paginator(avisos, 10)
        page_obj = paginator.get_page(page)

        serializer = AvisoListSerializer(page_obj.object_list, many=True)
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
            {"error": f"Erro ao listar avisos: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def aviso_home_view(request):
    """Retorna avisos vigentes para exibir na Home do usuário."""
    try:
        user = request.user
        avisos = Aviso.objects.select_related("grupo", "created_by").all()
        # Define se é síndico pelo nome do grupo (aceita variação sem acento)
        is_sindico = user.groups.filter(
            Q(name__iexact="Síndicos") | Q(name__iexact="Sindicos")
        ).exists()
        # Admin que não é síndico não recebe avisos na Home
        if user.is_staff and not is_sindico:
            return Response([])
        # Demais perfis recebem por grupo e pelo condomínio do criador
        grupos_ids = list(user.groups.values_list("id", flat=True))
        avisos = avisos.filter(grupo_id__in=grupos_ids)
        if getattr(user, "condominio", None):
            avisos = avisos.filter(created_by__condominio=user.condominio)

        # Se for morador, filtrar avisos de encomenda apenas da sua unidade
        is_morador = user.groups.filter(name="Moradores").exists()
        if is_morador and getattr(user, "unidade", None):
            from ...models import Encomenda

            has_pending = Encomenda.objects.filter(
                unidade_id=user.unidade_id, retirado_em__isnull=True
            ).exists()

            if has_pending:
                avisos = avisos.filter(
                    Q(titulo__icontains="Nova encomenda")
                    & Q(titulo__icontains=user.unidade.identificacao_completa)
                    | ~Q(titulo__icontains="Nova encomenda")
                )
            else:
                avisos = avisos.filter(~Q(titulo__icontains="Nova encomenda"))

        from django.utils import timezone

        now = timezone.now()
        avisos = (
            avisos.filter(status=Aviso.STATUS_ATIVO, data_inicio__lte=now)
            .filter(Q(data_fim__gte=now) | Q(data_fim__isnull=True))
            .order_by("-prioridade", "-data_inicio")[:10]
        )

        serializer = AvisoListSerializer(avisos, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {"error": f"Erro ao buscar avisos: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStaffOrSindico])
def aviso_create_view(request):
    try:
        serializer = AvisoSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            aviso = serializer.save()
            return Response(
                AvisoSerializer(aviso).data, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {"error": f"Erro ao criar aviso: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def aviso_detail_view(request, pk):
    try:
        aviso = Aviso.objects.select_related("created_by").get(pk=pk)
        user = request.user
        # Garantir acesso: staff sempre pode; síndico só do seu condomínio; demais por grupo e condomínio
        if not user.is_staff:
            is_sindico = user.groups.filter(
                Q(name__iexact="Síndicos") | Q(name__iexact="Sindicos")
            ).exists()
            same_condo = True
            if getattr(user, "condominio", None):
                same_condo = (
                    getattr(
                        getattr(aviso, "created_by", None), "condominio", None
                    )
                    == user.condominio
                )
            if is_sindico:
                if not same_condo:
                    return Response(
                        {
                            "error": "Você não tem permissão para ver este aviso."
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
            else:
                if (
                    not user.groups.filter(id=aviso.grupo_id).exists()
                    or not same_condo
                ):
                    return Response(
                        {
                            "error": "Você não tem permissão para ver este aviso."
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
        return Response(AvisoSerializer(aviso).data)
    except Aviso.DoesNotExist:
        return Response(
            {"error": "Aviso não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao obter aviso: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsStaffOrSindico])
def aviso_update_view(request, pk):
    try:
        aviso = Aviso.objects.get(pk=pk)
        serializer = AvisoSerializer(
            aviso,
            data=request.data,
            partial=(request.method == "PATCH"),
            context={"request": request},
        )
        if serializer.is_valid():
            aviso = serializer.save()
            return Response(AvisoSerializer(aviso).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Aviso.DoesNotExist:
        return Response(
            {"error": "Aviso não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao atualizar aviso: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsStaffOrSindico])
def aviso_delete_view(request, pk):
    try:
        aviso = Aviso.objects.get(pk=pk)
        aviso.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except Aviso.DoesNotExist:
        return Response(
            {"error": "Aviso não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao excluir aviso: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffOrSindico])
def aviso_grupos_options_view(request):
    """Lista grupos disponíveis (exceto 'admin') para seleção ao criar avisos."""
    try:
        grupos = Group.objects.exclude(name__iexact="admin").order_by("name")
        serializer = AvisoOptionsSerializer(grupos, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {"error": f"Erro ao listar grupos: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
