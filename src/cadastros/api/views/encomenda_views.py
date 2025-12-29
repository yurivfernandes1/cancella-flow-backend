from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Aviso, Encomenda
from ..serializers import EncomendaListSerializer, EncomendaSerializer


def criar_aviso_encomenda(encomenda, criador):
    """
    Cria um aviso automático para o morador responsável pela unidade.
    Somente cria o aviso se a unidade tiver um morador associado.
    """
    try:
        # Verificar se a unidade tem pelo menos um morador associado (relação reversa)
        if not encomenda.unidade.morador.all().exists():
            return

        # Buscar grupo Moradores
        grupo_moradores = Group.objects.filter(name="Moradores").first()
        if not grupo_moradores:
            return

        # Criar o aviso
        titulo = (
            f"Nova encomenda para {encomenda.unidade.identificacao_completa}"
        )
        descricao = (
            f"Uma encomenda foi registrada para {encomenda.destinatario_nome}."
        )
        if encomenda.descricao:
            descricao += f" Descrição: {encomenda.descricao}"
        if encomenda.codigo_rastreio:
            descricao += f" Código de rastreio: {encomenda.codigo_rastreio}"
        descricao += " A encomenda está disponível para retirada na portaria."

        now = timezone.now()
        data_fim = now + timezone.timedelta(
            days=30
        )  # Aviso válido por 30 dias

        Aviso.objects.create(
            titulo=titulo,
            descricao=descricao,
            grupo=grupo_moradores,
            prioridade=Aviso.PRIORIDADE_MEDIA,
            status=Aviso.STATUS_ATIVO,
            data_inicio=now,
            data_fim=data_fim,
            created_by=criador,
        )
    except Exception as e:
        # Não deve interromper a criação da encomenda se falhar
        print(f"Erro ao criar aviso de encomenda: {str(e)}")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def encomenda_list_view(request):
    """
    Lista encomendas com paginação e busca.
    Por padrão, retorna apenas encomendas NÃO entregues (sem data de retirada).

    Parâmetros opcionais:
    - search: busca em vários campos
    - incluir_entregues: "true" para incluir encomendas já entregues
    - unidade_antiga: ID da unidade para buscar encomendas antigas (entregues)
    - codigo_antiga: código de rastreio para buscar encomenda antiga específica

    Controle de acesso:
    - Portaria/Staff: vê todas as encomendas (filtradas pelo condomínio)
    - Moradores: veem apenas encomendas da sua unidade
    """
    try:
        user = request.user

        # Parâmetros de busca
        search = request.GET.get("search", "")
        incluir_entregues = (
            request.GET.get("incluir_entregues", "false").lower() == "true"
        )
        unidade_antiga = request.GET.get("unidade_antiga", "")
        codigo_antiga = request.GET.get("codigo_antiga", "")

        # 'morador' é relação reversa em Unidade; não pode usar select_related
        encomendas = (
            Encomenda.objects.select_related("unidade")
            .prefetch_related("unidade__morador")
            .all()
        )

        # Controle de acesso por grupo
        is_portaria = user.groups.filter(name="Portaria").exists()
        is_morador = user.groups.filter(name="Moradores").exists()

        # Filtrar por condomínio do usuário para Portaria (exceto staff)
        if (
            is_portaria
            and not user.is_staff
            and getattr(user, "condominio_id", None)
        ):
            encomendas = encomendas.filter(
                created_by__condominio_id=user.condominio_id
            )
        elif is_morador and not (user.is_staff or is_portaria):
            # Moradores veem apenas encomendas da sua unidade
            if user.unidade_id:
                encomendas = encomendas.filter(unidade_id=user.unidade_id)
            else:
                encomendas = Encomenda.objects.none()
        elif not (user.is_staff or is_portaria):
            # Usuários sem permissão não veem nada
            encomendas = Encomenda.objects.none()

        # FILTRO PRINCIPAL: Por padrão, mostrar apenas não entregues
        # Exceção: se buscar por unidade_antiga ou codigo_antiga, incluir entregues
        if unidade_antiga:
            # Buscar encomendas entregues de uma unidade específica
            encomendas = encomendas.filter(
                unidade_id=unidade_antiga, retirado_em__isnull=False
            )
        elif codigo_antiga:
            # Buscar encomenda específica pelo código (entregue ou não)
            encomendas = encomendas.filter(
                codigo_rastreio__icontains=codigo_antiga
            )
        elif not incluir_entregues:
            # Padrão: apenas não entregues
            encomendas = encomendas.filter(retirado_em__isnull=True)
        # Se incluir_entregues=true, não aplica filtro (mostra todas)

        if search:
            encomendas = encomendas.filter(
                Q(descricao__icontains=search)
                | Q(codigo_rastreio__icontains=search)
                | Q(destinatario_nome__icontains=search)
                | Q(unidade__numero__icontains=search)
                | Q(unidade__bloco__icontains=search)
                | Q(retirado_por__icontains=search)
            )

        # Ordenação
        encomendas = encomendas.order_by("-created_on")

        # Paginação
        page = int(request.GET.get("page", 1))
        paginator = Paginator(encomendas, 10)
        page_obj = paginator.get_page(page)

        serializer = EncomendaListSerializer(page_obj.object_list, many=True)

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
            {"error": f"Erro ao listar encomendas: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def encomenda_create_view(request):
    """
    Cria uma nova encomenda.
    Apenas Portaria e Administradores podem criar.
    Cria automaticamente um aviso para o morador responsável pela unidade.
    """
    try:
        user = request.user
        is_portaria = user.groups.filter(name="Portaria").exists()

        if not (user.is_staff or is_portaria):
            return Response(
                {"error": "Apenas Portaria pode cadastrar encomendas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = EncomendaSerializer(data=request.data)
        if serializer.is_valid():
            encomenda = serializer.save(created_by=user)

            # Criar aviso automático para o morador da unidade
            criar_aviso_encomenda(encomenda, user)

            return Response(
                EncomendaSerializer(encomenda).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {"error": f"Erro ao criar encomenda: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def encomenda_detail_view(request, pk):
    """
    Obtém detalhes de uma encomenda específica
    """
    try:
        encomenda = Encomenda.objects.select_related("unidade").get(pk=pk)
        user = request.user
        is_portaria = user.groups.filter(name="Portaria").exists()
        is_morador = user.groups.filter(name="Moradores").exists()

        # Moradores só podem ver encomendas da sua unidade
        if is_morador and not (user.is_staff or is_portaria):
            if (
                user.unidade_id is None
                or user.unidade_id != encomenda.unidade_id
            ):
                return Response(
                    {
                        "error": "Você não tem permissão para ver esta encomenda."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = EncomendaSerializer(encomenda)
        return Response(serializer.data)

    except Encomenda.DoesNotExist:
        return Response(
            {"error": "Encomenda não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao obter encomenda: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def encomenda_update_view(request, pk):
    """
    Atualiza uma encomenda.
    Apenas Portaria e Administradores podem editar.
    """
    try:
        user = request.user
        is_portaria = user.groups.filter(name="Portaria").exists()

        if not (user.is_staff or is_portaria):
            return Response(
                {"error": "Apenas Portaria pode editar encomendas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        encomenda = Encomenda.objects.get(pk=pk)
        serializer = EncomendaSerializer(
            encomenda, data=request.data, partial=(request.method == "PATCH")
        )

        if serializer.is_valid():
            encomenda = serializer.save(updated_by=user)
            return Response(EncomendaSerializer(encomenda).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Encomenda.DoesNotExist:
        return Response(
            {"error": "Encomenda não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao atualizar encomenda: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def encomenda_delete_view(request, pk):
    """
    Exclui uma encomenda.
    Apenas Administradores podem excluir.
    """
    try:
        user = request.user

        if not user.is_staff:
            return Response(
                {"error": "Apenas administradores podem excluir encomendas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        encomenda = Encomenda.objects.get(pk=pk)
        encomenda.delete()

        return Response(
            {"message": "Encomenda excluída com sucesso."},
            status=status.HTTP_204_NO_CONTENT,
        )

    except Encomenda.DoesNotExist:
        return Response(
            {"error": "Encomenda não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao excluir encomenda: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def encomenda_badge_view(request):
    """
    Retorna um resumo para o badge de encomendas pendentes do morador.
    Considera como pendentes as encomendas sem data de retirada (retirado_em nulo).

    Buckets por idade da criação (created_on):
      - green: 0 dias (hoje)
      - yellow: 1 a 3 dias
      - red: 4+ dias

    Para moradores, filtra pela unidade vinculada ao usuário.
    Para staff/portaria, é possível filtrar por ?unidade_id=<id> (opcional).
    """
    try:
        user = request.user
        now = timezone.now()

        qs = Encomenda.objects.select_related("unidade").filter(
            retirado_em__isnull=True
        )

        is_portaria = user.groups.filter(name="Portaria").exists()
        is_morador = user.groups.filter(name="Moradores").exists()

        if is_morador and not (user.is_staff or is_portaria):
            # Morador: apenas encomendas da própria unidade
            if user.unidade_id:
                qs = qs.filter(unidade_id=user.unidade_id)
            else:
                qs = qs.none()
        else:
            # Staff/Portaria: pode filtrar por unidade_id opcionalmente
            unidade_id = request.GET.get("unidade_id")
            if unidade_id:
                qs = qs.filter(unidade_id=unidade_id)
            # Caso não informe, mantemos todas (útil para dashboards gerais)

        total = qs.count()

        green = yellow = red = 0
        if total > 0:
            for enc in qs.only("created_on"):
                delta_days = (now - enc.created_on).days
                if delta_days <= 0:
                    green += 1
                elif 1 <= delta_days <= 3:
                    yellow += 1
                else:
                    red += 1

        # Cor do badge: priorizar mais antigo (vermelho > amarelo > verde)
        if total == 0:
            badge_color = "none"
        elif red > 0:
            badge_color = "red"
        elif yellow > 0:
            badge_color = "yellow"
        else:
            badge_color = "green"

        return Response(
            {
                "total": total,
                "green": green,
                "yellow": yellow,
                "red": red,
                "badge_color": badge_color,
            }
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao calcular badge de encomendas: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
