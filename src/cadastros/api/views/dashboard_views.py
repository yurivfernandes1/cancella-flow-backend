import logging
from datetime import timedelta

from access.models import User
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Aviso, Encomenda, EspacoReserva, Evento, Visitante

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def morador_stats_view(request):
    """
    Retorna estatísticas do dashboard do morador:
    - Encomendas pendentes (não retiradas) com idade em dias e cor do alerta
    - Visitantes cadastrados
    - Avisos ativos
    - Reservas futuras confirmadas
    """
    try:
        user = request.user
        now = timezone.now()

        # Verificar se é morador
        is_morador = user.groups.filter(name="Moradores").exists()
        if not is_morador:
            return Response(
                {"error": "Acesso permitido apenas para moradores."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 1. ENCOMENDAS PENDENTES (não retiradas)
        try:
            encomendas_pendentes = Encomenda.objects.filter(
                unidade__morador=user, retirado_em__isnull=True
            ).order_by("created_on")

            # Calcular a encomenda mais antiga e definir cor do alerta
            encomendas_count = encomendas_pendentes.count()
            dias_mais_antiga = 0
            cor_alerta = "#2abb98"  # Verde (padrão)

            if encomendas_count > 0:
                encomenda_mais_antiga = encomendas_pendentes.first()
                if encomenda_mais_antiga and encomenda_mais_antiga.created_on:
                    dias_mais_antiga = (
                        now - encomenda_mais_antiga.created_on
                    ).days

                # Definir cor baseada nos dias
                if dias_mais_antiga >= 2:
                    cor_alerta = "#ef4444"  # Vermelho (2+ dias)
                elif dias_mais_antiga >= 1:
                    cor_alerta = "#f59e0b"  # Amarelo (1 dia)
                # else: mantém verde (menos de 1 dia)
        except Exception:
            logger.exception(
                "Erro ao calcular encomendas pendentes do morador"
            )
            encomendas_count = 0
            dias_mais_antiga = 0
            cor_alerta = "#2abb98"

        # 2. VISITANTES CADASTRADOS (do morador)
        try:
            visitantes_count = Visitante.objects.filter(morador=user).count()
        except Exception:
            logger.exception("Erro ao calcular visitantes do morador")
            visitantes_count = 0

        # 3. AVISOS ATIVOS DO CONDOMÍNIO (filtrado por condomínio do morador)
        grupos_ids = list(user.groups.values_list("id", flat=True))
        try:
            avisos_query = Aviso.objects.filter(
                grupo_id__in=grupos_ids,
                status=Aviso.STATUS_ATIVO,
                data_inicio__lte=now,
            ).filter(Q(data_fim__gte=now) | Q(data_fim__isnull=True))

            # Filtrar por condomínio se o morador tiver condomínio
            if hasattr(user, "condominio") and user.condominio:
                avisos_query = avisos_query.filter(
                    created_by__isnull=False,
                    created_by__condominio=user.condominio,
                )

            avisos_count = avisos_query.count()
        except Exception:
            logger.exception("Erro ao calcular avisos do morador")
            avisos_count = 0

        # 4. RESERVAS FUTURAS (confirmadas ou pendentes do morador)
        try:
            reservas_count = EspacoReserva.objects.filter(
                morador=user,
                data_reserva__gte=now.date(),
                status__in=["confirmada", "pendente"],
            ).count()
        except Exception:
            logger.exception("Erro ao calcular reservas futuras do morador")
            reservas_count = 0

        # Montar resposta
        return Response(
            {
                "encomendas": {
                    "total": encomendas_count,
                    "dias_mais_antiga": dias_mais_antiga,
                    "cor_alerta": cor_alerta,
                },
                "visitantes": {"total": visitantes_count},
                "avisos": {"total": avisos_count},
                "reservas": {"total": reservas_count},
            }
        )

    except Exception as e:
        return Response(
            {"error": f"Erro ao buscar estatísticas: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sindico_stats_view(request):
    """
    Retorna estatísticas do dashboard do síndico:
    - Total de moradores e moradores ativos
    - Total de funcionários (portaria)
    - Visitantes do mês atual
    - Encomendas pendentes
    - Avisos ativos
    - Reservas confirmadas nos próximos 7 dias
    - Pendências (por ora, sempre 0)
    """
    try:
        user = request.user

        # Verificar se é síndico
        is_sindico = user.groups.filter(
            Q(name__iexact="Síndicos") | Q(name__iexact="Sindicos")
        ).exists()

        if not is_sindico:
            return Response(
                {"error": "Acesso permitido apenas para síndicos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Obter condomínio do síndico
        condominio_id = user.condominio_id
        if not condominio_id:
            return Response(
                {"error": "Síndico não está associado a um condomínio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. MORADORES
        try:
            moradores_total = User.objects.filter(
                condominio_id=condominio_id, groups__name="Moradores"
            ).count()

            moradores_ativos = User.objects.filter(
                condominio_id=condominio_id,
                groups__name="Moradores",
                is_active=True,
            ).count()

            percentual_ativos = (
                round((moradores_ativos / moradores_total) * 100)
                if moradores_total > 0
                else 0
            )
        except Exception:
            logger.exception("Erro ao calcular moradores do condomínio")
            moradores_total = 0
            moradores_ativos = 0
            percentual_ativos = 0

        # 2. FUNCIONÁRIOS (Portaria)
        try:
            funcionarios_total = User.objects.filter(
                condominio_id=condominio_id, groups__name="Portaria"
            ).count()
        except Exception:
            logger.exception("Erro ao calcular funcionários do condomínio")
            funcionarios_total = 0

        # 3. VISITANTES DO MÊS ATUAL
        hoje = timezone.now()
        primeiro_dia_mes = hoje.replace(day=1)

        try:
            visitantes_mes = Visitante.objects.filter(
                morador__condominio_id=condominio_id,
                created_on__gte=primeiro_dia_mes,
            ).count()
        except Exception:
            logger.exception("Erro ao calcular visitantes do mês")
            visitantes_mes = 0

        # 4. ENCOMENDAS PENDENTES (não retiradas) com cor por idade da mais antiga
        try:
            encomendas_qs = Encomenda.objects.filter(
                unidade__condominio_id=condominio_id, retirado_em__isnull=True
            ).order_by("created_on")

            encomendas_pendentes_total = encomendas_qs.count()
            dias_mais_antiga = 0
            cor_alerta_encomenda = "#2abb98"  # verde padrão (< 1 dia)

            if encomendas_pendentes_total > 0:
                encomenda_mais_antiga = encomendas_qs.first()
                if encomenda_mais_antiga and encomenda_mais_antiga.created_on:
                    dias_mais_antiga = (
                        timezone.now() - encomenda_mais_antiga.created_on
                    ).days

                # Regras de cor: > 3 dias = vermelho, >= 2 dias = amarelo, < 1 dia = verde
                if dias_mais_antiga > 3:
                    cor_alerta_encomenda = "#ef4444"
                elif dias_mais_antiga >= 2:
                    cor_alerta_encomenda = "#f59e0b"
                else:
                    cor_alerta_encomenda = "#2abb98"
        except Exception:
            logger.exception("Erro ao calcular encomendas pendentes")
            encomendas_pendentes_total = 0
            dias_mais_antiga = 0
            cor_alerta_encomenda = "#2abb98"

        # 5. AVISOS ATIVOS (vigentes)
        agora = timezone.now()
        try:
            avisos_ativos = (
                Aviso.objects.filter(
                    created_by__isnull=False,
                    created_by__condominio__id=condominio_id,
                    status=Aviso.STATUS_ATIVO,
                    data_inicio__lte=agora,
                )
                .filter(Q(data_fim__gte=agora) | Q(data_fim__isnull=True))
                .count()
            )
        except Exception:
            logger.exception("Erro ao calcular avisos ativos do condomínio")
            avisos_ativos = 0

        # 6. RESERVAS CONFIRMADAS NOS PRÓXIMOS 7 DIAS
        hoje_date = timezone.now().date()
        proximos_7_dias = hoje_date + timedelta(days=7)
        try:
            reservas_proximas = EspacoReserva.objects.filter(
                espaco__condominio_id=condominio_id,
                data_reserva__gte=hoje_date,
                data_reserva__lte=proximos_7_dias,
                status="confirmada",
            ).count()
        except Exception:
            logger.exception("Erro ao calcular reservas próximas")
            reservas_proximas = 0

        # 6b. EVENTOS PRÓXIMOS (próximos 7 dias) do condomínio do síndico
        try:
            eventos_proximos = Evento.objects.filter(
                created_by__isnull=False,
                created_by__condominio_id=condominio_id,
                data_evento__gte=hoje_date,
                data_evento__lte=proximos_7_dias,
            ).count()
        except Exception:
            logger.exception("Erro ao calcular eventos próximos")
            eventos_proximos = 0

        # 7. PENDÊNCIAS (por ora, sempre 0 conforme solicitado)
        pendencias = 0

        return Response(
            {
                "moradores": {
                    "total": moradores_total,
                    "ativos": moradores_ativos,
                    "percentual_ativos": percentual_ativos,
                },
                "funcionarios": {"total": funcionarios_total},
                "visitantes_mes": {"total": visitantes_mes},
                "encomendas_pendentes": {
                    "total": encomendas_pendentes_total,
                    "dias_mais_antiga": dias_mais_antiga,
                    "cor_alerta": cor_alerta_encomenda,
                },
                "avisos_ativos": {"total": avisos_ativos},
                "reservas_proximas": {"total": reservas_proximas},
                "eventos_proximos": {"total": eventos_proximos},
                "pendencias": {"total": pendencias},
            }
        )

    except Exception as e:
        return Response(
            {"error": f"Erro ao buscar estatísticas: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
