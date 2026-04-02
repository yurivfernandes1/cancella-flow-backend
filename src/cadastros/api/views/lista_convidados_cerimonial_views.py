import base64
import io
import json
import urllib.request

import qrcode
from django.conf import settings as django_settings
from django.db.models import Max, Q
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from ...models import (
    RESPOSTA_PRESENCA_CONFIRMADO,
    RESPOSTA_PRESENCA_RECUSADO,
    ConvidadoListaCerimonial,
    EventoCerimonial,
    EventoCerimonialFuncionario,
    ListaConvidadosCerimonial,
)
from ..serializers.lista_convidados_cerimonial_serializer import (
    ConvidadoListaCerimonialSerializer,
    ListaConvidadosCerimonialSerializer,
)
from .evento_cerimonial_views import (
    _is_cerimonialista,
    _is_organizador,
    _is_participante_evento,
    _is_recepcao,
)


def _pode_editar_lista(user, evento):
    if user.is_staff:
        return True
    return (
        evento.cerimonialistas.filter(id=user.id).exists()
        or evento.organizadores.filter(id=user.id).exists()
    )


def _pode_confirmar_entrada(user, evento):
    if user.is_staff:
        return True
    if _is_recepcao(user) and evento.funcionarios.filter(id=user.id).exists():
        return True
    return evento.cerimonialistas.filter(id=user.id).exists()


def _evento_em_andamento(evento, referencia=None):
    if not evento.datetime_inicio or not evento.datetime_fim:
        return False
    referencia = referencia or timezone.localtime()
    inicio_local = timezone.localtime(evento.datetime_inicio)
    fim_local = timezone.localtime(evento.datetime_fim)
    return inicio_local <= referencia <= fim_local


def _validar_operacao_recepcao(user, evento, requer_horario=False):
    # Cerimonialistas e administradores mantêm a permissão operacional antiga.
    if user.is_staff or _is_cerimonialista(user):
        return None

    if not _is_recepcao(user):
        return None

    vinculo_ativo = (
        EventoCerimonialFuncionario.objects.select_related("evento")
        .filter(
            usuario=user,
            horario_entrada__isnull=False,
            horario_saida__isnull=True,
        )
        .order_by("-horario_entrada", "-id")
        .first()
    )

    if not vinculo_ativo:
        return Response(
            {
                "error": "Faça check-in no evento para iniciar a leitura e validação de convidados."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if vinculo_ativo.evento_id != evento.id:
        return Response(
            {
                "error": "Você possui check-in ativo em outro evento.",
                "evento_ativo": vinculo_ativo.evento.nome,
                "evento_ativo_id": vinculo_ativo.evento_id,
            },
            status=status.HTTP_409_CONFLICT,
        )

    if requer_horario and not _evento_em_andamento(evento):
        return Response(
            {
                "error": "A leitura de convidados só é permitida na data e horário do evento."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return None


def _resposta_presenca_label(value):
    if value == RESPOSTA_PRESENCA_CONFIRMADO:
        return "Confirmado"
    if value == RESPOSTA_PRESENCA_RECUSADO:
        return "Recusado"
    return "Pendente"


def _normalizar_resposta_presenca(value):
    raw = str(value or "").strip().lower()
    if raw in {"confirmar", "confirmado", "sim", "yes", "aceitar"}:
        return RESPOSTA_PRESENCA_CONFIRMADO
    if raw in {"recusar", "recusado", "nao", "não", "negar", "no"}:
        return RESPOSTA_PRESENCA_RECUSADO
    return None


def _build_rsvp_url(request, token, resposta):
    path = reverse(
        "lista-convidados-cerimonial-rsvp-public",
        kwargs={"token": token},
    )
    return request.build_absolute_uri(f"{path}?resposta={resposta}")


def _enviar_qrcode_email_cerimonial(convidado, lista):
    try:
        import resend
    except Exception:
        return False
    if not convidado.email:
        return False

    api_key = django_settings.RESEND_API_KEY
    email_from = django_settings.EMAIL_FROM
    if not api_key:
        return False

    evento = lista.evento
    data_evento = (
        evento.datetime_inicio.strftime("%d/%m/%Y %H:%M")
        if evento.datetime_inicio
        else "A confirmar"
    )

    endereco = ""
    try:
        from ..serializers.evento_cerimonial_serializer import (
            EventoCerimonialSerializer,
        )

        endereco = EventoCerimonialSerializer().get_endereco_completo(evento)
    except Exception:
        endereco = ""

    img = qrcode.make(str(convidado.qr_token))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    html_body = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:620px;margin:0 auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;\">
      <div style=\"background:#19294a;padding:20px 24px;text-align:center;\">
        <p style=\"color:#ffffff;margin:0;font-size:1rem;font-weight:600;\">Convite para Evento</p>
      </div>
      <div style=\"padding:24px;background:#ffffff;\">
        <h2 style=\"color:#19294a;margin:0 0 12px;font-size:1.1rem;\">Olá, {convidado.nome}!</h2>
        <p style=\"color:#374151;line-height:1.6;margin:0 0 16px;\">
          Você foi convidado(a) para o evento:<br/>
          <strong style=\"font-size:1.05rem;color:#2abb98;\">{evento.nome}</strong>
        </p>
        <table style=\"width:100%;border-collapse:collapse;margin:0 0 20px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;\">
          <tr>
            <td style=\"padding:8px 12px;color:#6b7280;font-size:0.88rem;width:120px;\">Data</td>
            <td style=\"padding:8px 12px;color:#111827;font-weight:500;\">{data_evento}</td>
          </tr>
          <tr>
            <td style=\"padding:8px 12px;color:#6b7280;font-size:0.88rem;width:120px;\">Local</td>
            <td style=\"padding:8px 12px;color:#111827;font-weight:500;\">{endereco or "-"}</td>
          </tr>
        </table>
        <div style=\"background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:16px 20px;text-align:center;\">
          <p style=\"color:#15803d;font-weight:600;font-size:1rem;margin:0 0 8px;\">QR Code de Acesso</p>
          <p style=\"color:#166534;font-size:0.88rem;margin:0 0 12px;\">Apresente-o na recepção para confirmar sua entrada.</p>
          <img src=\"cid:qrcode\" alt=\"QR Code de Acesso\" style=\"width:200px;height:200px;border-radius:8px;\" />
        </div>
      </div>
    </div>
    """

    try:
        resend.api_key = api_key
        resend.Emails.send(
            {
                "from": email_from,
                "to": [convidado.email],
                "subject": f"Seu convite para {evento.nome}",
                "html": html_body,
                "attachments": [
                    {
                        "filename": "qrcode.png",
                        "content": qr_base64,
                        "content_id": "qrcode",
                        "disposition": "inline",
                    }
                ],
            }
        )
        return True
    except Exception:
        return False


def _enviar_confirmacao_presenca_email_cerimonial(request, convidado, lista):
    try:
        import resend
    except Exception:
        return False

    if not convidado.email:
        return False

    api_key = django_settings.RESEND_API_KEY
    email_from = django_settings.EMAIL_FROM
    if not api_key:
        return False

    evento = lista.evento
    data_evento = (
        evento.datetime_inicio.strftime("%d/%m/%Y %H:%M")
        if evento.datetime_inicio
        else "A confirmar"
    )

    endereco = ""
    try:
        from ..serializers.evento_cerimonial_serializer import (
            EventoCerimonialSerializer,
        )

        endereco = EventoCerimonialSerializer().get_endereco_completo(evento)
    except Exception:
        endereco = ""

    confirmar_url = _build_rsvp_url(
        request,
        convidado.qr_token,
        RESPOSTA_PRESENCA_CONFIRMADO,
    )
    recusar_url = _build_rsvp_url(
        request,
        convidado.qr_token,
        RESPOSTA_PRESENCA_RECUSADO,
    )

    evento_imagem_html = ""
    attachments = []
    if evento.imagem_db_data:
        evento_img_b64 = base64.b64encode(evento.imagem_db_data).decode()
        evento_img_filename = (
            evento.imagem_db_filename or f"evento-{evento.id}-imagem.jpg"
        )
        attachments.append(
            {
                "filename": evento_img_filename,
                "content": evento_img_b64,
                "content_id": "evento_imagem",
                "disposition": "inline",
            }
        )
        evento_imagem_html = """
        <div style="margin:0 0 18px;">
          <p style="color:#334155;font-size:0.88rem;font-weight:600;margin:0 0 8px;">Imagem do evento</p>
          <img src="cid:evento_imagem" alt="Imagem do evento" style="width:100%;max-height:260px;object-fit:cover;border-radius:10px;border:1px solid #e5e7eb;" />
        </div>
        """

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
      <div style="background:#19294a;padding:20px 24px;text-align:center;">
        <p style="color:#ffffff;margin:0;font-size:1rem;font-weight:600;">Confirmação de Presença</p>
      </div>
      <div style="padding:24px;background:#ffffff;">
        <h2 style="color:#19294a;margin:0 0 12px;font-size:1.1rem;">Olá, {convidado.nome}!</h2>
        <p style="color:#374151;line-height:1.6;margin:0 0 16px;">
          Você foi convidado(a) para o evento:<br/>
          <strong style="font-size:1.05rem;color:#2abb98;">{evento.nome}</strong>
        </p>
                {evento_imagem_html}
        <table style="width:100%;border-collapse:collapse;margin:0 0 20px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">
          <tr>
            <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:120px;">Data</td>
            <td style="padding:8px 12px;color:#111827;font-weight:500;">{data_evento}</td>
          </tr>
          <tr>
            <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:120px;">Local</td>
            <td style="padding:8px 12px;color:#111827;font-weight:500;">{endereco or "-"}</td>
          </tr>
        </table>
        <p style="color:#1f2937;line-height:1.6;margin:0 0 12px;">Por favor, confirme sua presença clicando em um dos botões abaixo:</p>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <a href="{confirmar_url}" style="background:#16a34a;color:#fff;text-decoration:none;padding:10px 14px;border-radius:8px;font-weight:600;font-size:0.88rem;">Confirmar presença</a>
          <a href="{recusar_url}" style="background:#dc2626;color:#fff;text-decoration:none;padding:10px 14px;border-radius:8px;font-weight:600;font-size:0.88rem;">Não poderei ir</a>
        </div>
        <p style="color:#64748b;font-size:0.8rem;margin:14px 0 0;">Após confirmar presença, você receberá por e-mail o QR Code de acesso.</p>
      </div>
    </div>
    """

    try:
        resend.api_key = api_key
        resend.Emails.send(
            {
                "from": email_from,
                "to": [convidado.email],
                "subject": f"Confirme sua presença em {evento.nome}",
                "html": html_body,
                "attachments": attachments,
            }
        )
        return True
    except Exception:
        return False


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _lista_atingiu_limite(lista):
    limite = max(int(lista.evento.numero_pessoas or 0), 0)
    if limite <= 0:
        return False, limite

    total = ConvidadoListaCerimonial.objects.filter(lista=lista).count()
    return total >= limite, limite


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def listas_convidados_cerimonial_view(request):
    user = request.user

    if request.method == "GET":
        qs = ListaConvidadosCerimonial.objects.select_related(
            "evento"
        ).prefetch_related(
            "convidados",
            "evento__cerimonialistas",
            "evento__organizadores",
            "evento__funcionarios",
        )

        if not user.is_staff:
            qs = qs.filter(
                Q(evento__cerimonialistas=user)
                | Q(evento__organizadores=user)
                | Q(evento__funcionarios=user)
            ).distinct()

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(titulo__icontains=search)
                | Q(evento__nome__icontains=search)
                | Q(convidados__nome__icontains=search)
            ).distinct()

        data_evento = request.query_params.get("data_evento", "").strip()
        if data_evento:
            qs = qs.filter(data_evento=data_evento)

        serializer = ListaConvidadosCerimonialSerializer(
            qs.order_by("-created_on"), many=True
        )
        return Response(serializer.data)

    if not (
        _is_cerimonialista(user) or _is_organizador(user) or user.is_staff
    ):
        return Response(
            {"error": "Sem permissão para criar lista de convidados."},
            status=status.HTTP_403_FORBIDDEN,
        )

    evento_id = request.data.get("evento")
    if not evento_id:
        return Response(
            {"error": "Informe o evento da lista."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        evento = EventoCerimonial.objects.prefetch_related(
            "cerimonialistas", "organizadores", "funcionarios"
        ).get(pk=evento_id)
    except EventoCerimonial.DoesNotExist:
        return Response(
            {"error": "Evento não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_editar_lista(user, evento):
        return Response(
            {"error": "Sem permissão para criar lista neste evento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    lista, created = ListaConvidadosCerimonial.objects.get_or_create(
        evento=evento,
        defaults={
            "titulo": str(
                request.data.get("titulo")
                or f"Lista de Convidados - {evento.nome}"
            ),
            "descricao": str(request.data.get("descricao") or ""),
            "data_evento": request.data.get("data_evento")
            or (
                evento.datetime_inicio.date()
                if evento.datetime_inicio
                else None
            ),
            "ativa": True,
        },
    )

    serializer = ListaConvidadosCerimonialSerializer(lista)
    return Response(
        serializer.data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def lista_convidados_cerimonial_detail_view(request, lista_pk):
    try:
        lista = (
            ListaConvidadosCerimonial.objects.select_related("evento")
            .prefetch_related(
                "convidados",
                "evento__cerimonialistas",
                "evento__organizadores",
                "evento__funcionarios",
            )
            .get(pk=lista_pk)
        )
    except ListaConvidadosCerimonial.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    evento = lista.evento

    if request.method == "GET":
        if not _is_participante_evento(request.user, evento):
            return Response(
                {"error": "Sem permissão."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(ListaConvidadosCerimonialSerializer(lista).data)

    if request.method == "PATCH":
        if not _pode_editar_lista(request.user, evento):
            return Response(
                {"error": "Sem permissão para editar esta lista."},
                status=status.HTTP_403_FORBIDDEN,
            )

        for field in ("titulo", "descricao", "data_evento", "ativa"):
            if field in request.data:
                setattr(lista, field, request.data[field])
        lista.save()
        return Response(ListaConvidadosCerimonialSerializer(lista).data)

    if not _pode_editar_lista(request.user, evento):
        return Response(
            {"error": "Sem permissão para excluir esta lista."},
            status=status.HTTP_403_FORBIDDEN,
        )
    lista.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def adicionar_convidado_cerimonial_view(request, lista_pk):
    try:
        lista = (
            ListaConvidadosCerimonial.objects.select_related("evento")
            .prefetch_related(
                "evento__cerimonialistas", "evento__organizadores"
            )
            .get(pk=lista_pk)
        )
    except ListaConvidadosCerimonial.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_editar_lista(request.user, lista.evento):
        return Response(
            {"error": "Sem permissão."},
            status=status.HTTP_403_FORBIDDEN,
        )

    cpf_raw = request.data.get("cpf", "")
    cpf_digits = "".join(c for c in str(cpf_raw) if c.isdigit())
    nome = str(request.data.get("nome", "")).strip()
    email = str(request.data.get("email", "")).strip()
    vip = _to_bool(request.data.get("vip", False))
    enviar_email = _to_bool(request.data.get("enviar_email", True))

    if cpf_digits and len(cpf_digits) != 11:
        return Response(
            {"error": "CPF deve ter 11 dígitos."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not nome:
        return Response(
            {"error": "Nome do convidado é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not email:
        return Response(
            {
                "error": "E-mail é obrigatório para enviar a confirmação de presença."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    atingiu_limite, limite = _lista_atingiu_limite(lista)
    if atingiu_limite:
        return Response(
            {
                "error": f"Limite de convidados atingido para este evento ({limite})."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if (
        cpf_digits
        and ConvidadoListaCerimonial.objects.filter(
            lista=lista, cpf=cpf_digits
        ).exists()
    ):
        return Response(
            {"error": "Este CPF já está na lista."},
            status=status.HTTP_409_CONFLICT,
        )

    convidado = ConvidadoListaCerimonial.objects.create(
        lista=lista,
        cpf=cpf_digits or None,
        nome=nome,
        email=email,
        vip=vip,
        created_by=request.user,
    )

    if not enviar_email:
        response_data = ConvidadoListaCerimonialSerializer(convidado).data
        response_data["confirmacao_email_enviado"] = False
        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
        )

    confirmacao_email_enviado = _enviar_confirmacao_presenca_email_cerimonial(
        request, convidado, lista
    )
    if not confirmacao_email_enviado:
        convidado.delete()
        return Response(
            {
                "error": "Não foi possível enviar o e-mail de confirmação. O convidado não foi adicionado."
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    response_data = ConvidadoListaCerimonialSerializer(convidado).data
    response_data["confirmacao_email_enviado"] = True

    return Response(
        response_data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def finalizar_lista_convidados_cerimonial_view(request, lista_pk):
    try:
        lista = (
            ListaConvidadosCerimonial.objects.select_related("evento")
            .prefetch_related(
                "convidados",
                "evento__cerimonialistas",
                "evento__organizadores",
            )
            .get(pk=lista_pk)
        )
    except ListaConvidadosCerimonial.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_editar_lista(request.user, lista.evento):
        return Response(
            {"error": "Sem permissão para finalizar esta lista."},
            status=status.HTTP_403_FORBIDDEN,
        )

    convidados = list(lista.convidados.all())
    if not convidados:
        return Response(
            {"error": "A lista não possui convidados para envio."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    enviados_confirmacao = 0
    enviados_qr = 0
    falhas = []

    for convidado in convidados:
        if not convidado.email:
            falhas.append(
                {
                    "convidado_id": convidado.id,
                    "nome": convidado.nome,
                    "erro": "Convidado sem e-mail cadastrado.",
                }
            )
            continue

        if convidado.resposta_presenca == RESPOSTA_PRESENCA_CONFIRMADO:
            enviado = _enviar_qrcode_email_cerimonial(convidado, lista)
            if enviado:
                enviados_qr += 1
            else:
                falhas.append(
                    {
                        "convidado_id": convidado.id,
                        "nome": convidado.nome,
                        "erro": "Não foi possível enviar o QR Code.",
                    }
                )
            continue

        enviado = _enviar_confirmacao_presenca_email_cerimonial(
            request, convidado, lista
        )
        if enviado:
            enviados_confirmacao += 1
        else:
            falhas.append(
                {
                    "convidado_id": convidado.id,
                    "nome": convidado.nome,
                    "erro": "Não foi possível enviar o e-mail de confirmação.",
                }
            )

    return Response(
        {
            "success": len(falhas) == 0,
            "total_convidados": len(convidados),
            "enviados_confirmacao": enviados_confirmacao,
            "enviados_qr": enviados_qr,
            "falhas": falhas,
        }
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def atualizar_convidado_cerimonial_view(request, lista_pk, convidado_pk):
    try:
        lista = (
            ListaConvidadosCerimonial.objects.select_related("evento")
            .prefetch_related(
                "evento__cerimonialistas", "evento__organizadores"
            )
            .get(pk=lista_pk)
        )
    except ListaConvidadosCerimonial.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_editar_lista(request.user, lista.evento):
        return Response(
            {"error": "Sem permissão."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        convidado = ConvidadoListaCerimonial.objects.get(
            pk=convidado_pk, lista=lista
        )
    except ConvidadoListaCerimonial.DoesNotExist:
        return Response(
            {"error": "Convidado não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if "cpf" in request.data:
        cpf_digits = "".join(
            c for c in str(request.data.get("cpf", "")) if c.isdigit()
        )
        if cpf_digits and len(cpf_digits) != 11:
            return Response(
                {"error": "CPF deve ter 11 dígitos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if cpf_digits and (
            ConvidadoListaCerimonial.objects.filter(
                lista=lista, cpf=cpf_digits
            )
            .exclude(pk=convidado.pk)
            .exists()
        ):
            return Response(
                {"error": "Este CPF já está na lista."},
                status=status.HTTP_409_CONFLICT,
            )
        convidado.cpf = cpf_digits or None

    if "nome" in request.data:
        nome = str(request.data.get("nome", "")).strip()
        if not nome:
            return Response(
                {"error": "Nome não pode ser vazio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        convidado.nome = nome

    if "email" in request.data:
        convidado.email = str(request.data.get("email", "")).strip()

    if "vip" in request.data:
        convidado.vip = _to_bool(request.data.get("vip"))

    convidado.save()
    return Response(ConvidadoListaCerimonialSerializer(convidado).data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remover_convidado_cerimonial_view(request, lista_pk, convidado_pk):
    try:
        lista = (
            ListaConvidadosCerimonial.objects.select_related("evento")
            .prefetch_related(
                "evento__cerimonialistas", "evento__organizadores"
            )
            .get(pk=lista_pk)
        )
    except ListaConvidadosCerimonial.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_editar_lista(request.user, lista.evento):
        return Response(
            {"error": "Sem permissão."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        convidado = ConvidadoListaCerimonial.objects.get(
            pk=convidado_pk, lista=lista
        )
    except ConvidadoListaCerimonial.DoesNotExist:
        return Response(
            {"error": "Convidado não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    convidado.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def confirmar_entrada_cerimonial_view(request, lista_pk, convidado_pk):
    try:
        lista = (
            ListaConvidadosCerimonial.objects.select_related("evento")
            .prefetch_related(
                "evento__cerimonialistas", "evento__funcionarios"
            )
            .get(pk=lista_pk)
        )
    except ListaConvidadosCerimonial.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_confirmar_entrada(request.user, lista.evento):
        return Response(
            {"error": "Sem permissão para confirmar entrada."},
            status=status.HTTP_403_FORBIDDEN,
        )

    erro_recepcao = _validar_operacao_recepcao(
        request.user,
        lista.evento,
        requer_horario=True,
    )
    if erro_recepcao:
        return erro_recepcao

    try:
        convidado = ConvidadoListaCerimonial.objects.get(
            pk=convidado_pk, lista=lista
        )
    except ConvidadoListaCerimonial.DoesNotExist:
        return Response(
            {"error": "Convidado não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if convidado.entrada_confirmada:
        if _is_recepcao(request.user) and not (
            request.user.is_staff or _is_cerimonialista(request.user)
        ):
            return Response(
                {
                    "error": "Somente o cerimonial pode cancelar entrada confirmada por engano da recepção."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        convidado.entrada_confirmada = False
        convidado.entrada_em = None
    else:
        convidado.entrada_confirmada = True
        convidado.entrada_em = timezone.now()
    convidado.save()

    return Response(ConvidadoListaCerimonialSerializer(convidado).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def enviar_qrcode_cerimonial_view(request, lista_pk, convidado_pk):
    try:
        lista = (
            ListaConvidadosCerimonial.objects.select_related("evento")
            .prefetch_related(
                "evento__cerimonialistas", "evento__organizadores"
            )
            .get(pk=lista_pk)
        )
    except ListaConvidadosCerimonial.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_editar_lista(request.user, lista.evento):
        return Response(
            {"error": "Sem permissão para enviar QR Code."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        convidado = ConvidadoListaCerimonial.objects.get(
            pk=convidado_pk, lista=lista
        )
    except ConvidadoListaCerimonial.DoesNotExist:
        return Response(
            {"error": "Convidado não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not convidado.email:
        return Response(
            {"error": "O convidado não possui e-mail cadastrado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if convidado.resposta_presenca != RESPOSTA_PRESENCA_CONFIRMADO:
        return Response(
            {
                "error": "Envio de QR Code permitido apenas para convidados com presença confirmada."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        enviado = _enviar_qrcode_email_cerimonial(convidado, lista)
    except Exception as exc:
        return Response(
            {"error": f"Falha ao enviar e-mail: {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    if not enviado:
        return Response(
            {"error": "Serviço de e-mail não configurado."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {"success": True, "message": "QR Code enviado com sucesso."}
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def buscar_cpf_simples_cerimonial_view(request):
    from django.contrib.auth import get_user_model

    User = get_user_model()

    cpf_raw = request.query_params.get("cpf", "")
    cpf_digits = "".join(c for c in str(cpf_raw) if c.isdigit())

    if len(cpf_digits) != 11:
        return Response(
            {"error": "CPF deve ter 11 dígitos."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cpf_fmt = f"{cpf_digits[:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-{cpf_digits[9:]}"
    usuario = (
        User.objects.filter(cpf=cpf_fmt).first()
        or User.objects.filter(cpf=cpf_digits).first()
    )
    if usuario:
        nome = (
            getattr(usuario, "full_name", None)
            or usuario.get_full_name()
            or usuario.username
        )
        return Response(
            {
                "cpf": cpf_digits,
                "nome": nome,
                "email": "",
                "encontrado": True,
                "fonte": "sistema",
            }
        )

    nome = None
    try:
        url = f"https://brasilapi.com.br/api/cpf/v1/{cpf_digits}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "CancellaFlow/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            nome = data.get("nome") or data.get("name")
    except Exception:
        nome = None

    return Response(
        {
            "cpf": cpf_digits,
            "nome": nome,
            "email": "",
            "encontrado": bool(nome),
            "fonte": "brasilapi" if nome else "",
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def convidados_anteriores_cerimonial_view(request):
    user = request.user
    q = request.query_params.get("q", "").strip()

    qs = ConvidadoListaCerimonial.objects.select_related(
        "lista", "lista__evento"
    )
    if not user.is_staff:
        qs = qs.filter(
            Q(lista__evento__cerimonialistas=user)
            | Q(lista__evento__organizadores=user)
        ).distinct()
        if _is_organizador(user) and not _is_cerimonialista(user):
            qs = qs.filter(created_by=user)

    if q:
        cpf_q = "".join(c for c in q if c.isdigit())
        if cpf_q:
            qs = qs.filter(cpf__icontains=cpf_q)
        else:
            qs = qs.filter(nome__icontains=q)

    latest_ids = (
        qs.exclude(Q(cpf__isnull=True) | Q(cpf=""))
        .values("cpf")
        .annotate(latest_id=Max("id"))
        .values_list("latest_id", flat=True)
    )
    sem_cpf_ids = qs.filter(Q(cpf__isnull=True) | Q(cpf="")).values_list(
        "id", flat=True
    )
    results = ConvidadoListaCerimonial.objects.filter(
        Q(id__in=latest_ids) | Q(id__in=sem_cpf_ids)
    ).order_by("nome")[:30]

    def _fmt(cpf):
        if len(cpf or "") == 11:
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf

    data = [
        {
            "cpf": c.cpf,
            "cpf_formatado": _fmt(c.cpf),
            "nome": c.nome,
            "email": c.email,
            "vip": c.vip,
        }
        for c in results
    ]
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirmar_por_qrcode_cerimonial_view(request):
    token = str(request.data.get("token", "")).strip()
    if not token:
        return Response(
            {"error": "Token é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        convidado = ConvidadoListaCerimonial.objects.select_related(
            "lista", "lista__evento"
        ).get(qr_token=token)
    except ConvidadoListaCerimonial.DoesNotExist:
        return Response(
            {"error": "QR code inválido."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _pode_confirmar_entrada(request.user, convidado.lista.evento):
        return Response(
            {"error": "Sem permissão para validar este QR code."},
            status=status.HTTP_403_FORBIDDEN,
        )

    erro_recepcao = _validar_operacao_recepcao(
        request.user,
        convidado.lista.evento,
        requer_horario=True,
    )
    if erro_recepcao:
        return erro_recepcao

    if convidado.entrada_confirmada:
        return Response(
            {
                "aviso": "Convidado já confirmou a entrada anteriormente.",
                "nome": convidado.nome,
                "lista": convidado.lista.titulo,
                "cpf": convidado.cpf,
            }
        )

    convidado.entrada_confirmada = True
    convidado.entrada_em = timezone.now()
    convidado.save()

    return Response(
        {
            "success": True,
            "nome": convidado.nome,
            "lista": convidado.lista.titulo,
            "cpf": convidado.cpf,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def resposta_presenca_public_cerimonial_view(request, token):
    resposta = _normalizar_resposta_presenca(
        request.query_params.get("resposta", "")
    )
    if resposta is None:
        return HttpResponse(
            "<h2>Resposta inválida</h2><p>Use os links de confirmação enviados por e-mail.</p>",
            status=400,
            content_type="text/html; charset=utf-8",
        )

    try:
        convidado = ConvidadoListaCerimonial.objects.select_related(
            "lista", "lista__evento"
        ).get(qr_token=token)
    except ConvidadoListaCerimonial.DoesNotExist:
        return HttpResponse(
            "<h2>Convite não encontrado</h2><p>Este link de confirmação é inválido ou expirou.</p>",
            status=404,
            content_type="text/html; charset=utf-8",
        )

    convidado.resposta_presenca = resposta
    convidado.resposta_presenca_em = timezone.now()
    convidado.save(update_fields=["resposta_presenca", "resposta_presenca_em"])

    qr_enviado = False
    if resposta == RESPOSTA_PRESENCA_CONFIRMADO:
        qr_enviado = _enviar_qrcode_email_cerimonial(
            convidado, convidado.lista
        )

    status_label = _resposta_presenca_label(convidado.resposta_presenca)
    titulo_resposta = "Resposta registrada com sucesso"
    resumo_resposta = "Obrigado por nos responder."
    mensagem_qr = ""
    mensagem_agradecimento = ""
    if resposta == RESPOSTA_PRESENCA_CONFIRMADO:
        titulo_resposta = "Presença confirmada"
        resumo_resposta = "Obrigado pela confirmação de presença."
        mensagem_agradecimento = (
            "<p style='margin:0 0 14px;color:#0f172a;font-weight:600;'>"
            "Sua confirmação foi recebida com sucesso. Agradecemos sua resposta."
            "</p>"
        )
        if qr_enviado:
            mensagem_qr = "<p style='color:#166534;'>Seu QR Code de acesso foi enviado para o seu e-mail.</p>"
        else:
            mensagem_qr = "<p style='color:#92400e;'>Não foi possível enviar o QR Code agora. Peça para o cerimonial reenviar pela lista de convidados.</p>"
    elif resposta == RESPOSTA_PRESENCA_RECUSADO:
        titulo_resposta = "Resposta registrada"
        resumo_resposta = "Obrigado por avisar sobre sua disponibilidade."

    evento_nome = convidado.lista.evento.nome
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:32px auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
      <div style="background:#19294a;padding:18px 22px;">
        <p style="margin:0;color:#fff;font-size:1rem;font-weight:700;">{titulo_resposta}</p>
      </div>
      <div style="padding:22px;background:#fff;">
        <h2 style="margin:0 0 8px;color:#0f172a;font-size:1.2rem;">{convidado.nome}</h2>
        <p style="margin:0 0 12px;color:#334155;">{resumo_resposta}</p>
        <p style="margin:0 0 6px;color:#334155;">Evento: <strong>{evento_nome}</strong></p>
        <p style="margin:0 0 16px;color:#334155;">Status da sua presença: <strong>{status_label}</strong></p>
        {mensagem_agradecimento}
        {mensagem_qr}
      </div>
    </div>
    """
    return HttpResponse(html, content_type="text/html; charset=utf-8")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_qrcode_cerimonial_view(request):
    from PIL import Image, ImageDraw, ImageFont

    token = request.query_params.get("token", "").strip()
    if not token:
        return Response(
            {"error": "Token é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        convidado = ConvidadoListaCerimonial.objects.select_related(
            "lista", "lista__evento"
        ).get(qr_token=token)
    except ConvidadoListaCerimonial.DoesNotExist:
        return Response(
            {"error": "QR code não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _is_participante_evento(request.user, convidado.lista.evento):
        return Response(
            {"error": "Sem permissão para baixar este QR code."},
            status=status.HTTP_403_FORBIDDEN,
        )

    qr_img = qrcode.make(str(token))
    qr_size = qr_img.size[0]

    padding = 20
    text_height = 50
    canvas_w = qr_size + (padding * 2)
    canvas_h = qr_size + (padding * 2) + text_height

    canvas = Image.new("RGB", (canvas_w, canvas_h), color="white")
    canvas.paste(qr_img, (padding, padding))

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("Arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    nome = convidado.nome
    bbox = draw.textbbox((0, 0), nome, font=font)
    text_w = bbox[2] - bbox[0]
    text_x = max((canvas_w - text_w) // 2, 10)
    text_y = qr_size + padding + 12
    draw.text((text_x, text_y), nome, fill="black", font=font)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    out.seek(0)

    filename = f"qrcode-{nome.replace(' ', '-').lower()}.png"
    response = HttpResponse(out.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


__all__ = [
    "listas_convidados_cerimonial_view",
    "lista_convidados_cerimonial_detail_view",
    "adicionar_convidado_cerimonial_view",
    "finalizar_lista_convidados_cerimonial_view",
    "atualizar_convidado_cerimonial_view",
    "remover_convidado_cerimonial_view",
    "confirmar_entrada_cerimonial_view",
    "enviar_qrcode_cerimonial_view",
    "buscar_cpf_simples_cerimonial_view",
    "convidados_anteriores_cerimonial_view",
    "confirmar_por_qrcode_cerimonial_view",
    "resposta_presenca_public_cerimonial_view",
    "download_qrcode_cerimonial_view",
]
