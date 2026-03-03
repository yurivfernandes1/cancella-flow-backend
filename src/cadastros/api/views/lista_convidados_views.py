import json
import urllib.error
import urllib.request

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import ConvidadoLista, ListaConvidados
from ..serializers.lista_convidados_serializer import (
    ConvidadoListaSerializer,
    ListaConvidadosSerializer,
)


def _is_morador(user):
    return user.groups.filter(name="Moradores").exists()


def _enviar_qrcode_email(convidado, lista):
    """
    Envia o QR code de acesso por e-mail ao convidado.
    Silencioso em caso de erro — não bloqueia o fluxo principal.
    Retorna True se enviado com sucesso.
    """
    import io

    import qrcode
    import resend
    from django.conf import settings as django_settings

    if not convidado.email:
        return False

    api_key = django_settings.RESEND_API_KEY
    email_from = django_settings.EMAIL_FROM
    if not api_key:
        return False

    try:
        morador = lista.morador
        condominio = getattr(morador, "condominio", None)
        condominio_nome = condominio.nome if condominio else "Condomínio"
        condominio_endereco = ""
        if condominio:
            partes = []
            if condominio.cep:
                partes.append(f"CEP {condominio.cep}")
            if condominio.numero:
                partes.append(f"n° {condominio.numero}")
            if condominio.complemento:
                partes.append(condominio.complemento)
            condominio_endereco = ", ".join(partes) if partes else ""

        local_descricao = ListaConvidadosSerializer().get_local_descricao(
            lista
        )

        img = qrcode.make(str(convidado.qr_token))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_bytes = list(buffer.getvalue())

        morador_nome = (
            getattr(morador, "full_name", None)
            or morador.get_full_name()
            or morador.username
        )
        data_evento_str = "A confirmar"
        if lista.data_evento:
            d = lista.data_evento
            data_evento_str = f"{d.day:02d}/{d.month:02d}/{d.year}"

        local_row = ""
        if local_descricao and local_descricao != "Local não informado":
            local_row = (
                '<tr style="background:#fff;">'
                '<td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:120px;">Local</td>'
                f'<td style="padding:8px 12px;color:#111827;font-weight:500;">{local_descricao}</td></tr>'
            )

        endereco_footer = ""
        if condominio_endereco:
            endereco_footer = f'<p style="color:#9ca3af;font-size:0.72rem;margin:2px 0 0;">{condominio_endereco}</p>'

        html_body = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
  <div style="background:#19294a;padding:20px 24px;text-align:center;">
    <p style="color:#ffffff;margin:0;font-size:1rem;font-weight:600;">{condominio_nome}</p>
  </div>
  <div style="padding:24px;background:#ffffff;">
    <h2 style="color:#19294a;margin:0 0 12px;font-size:1.1rem;">Ol&#225;, {convidado.nome}!</h2>
    <p style="color:#374151;line-height:1.6;margin:0 0 16px;">
      Voc&#234; foi convidado(a) por <strong>{morador_nome}</strong> para:<br/>
      <strong style="font-size:1.05rem;color:#2abb98;">{lista.titulo}</strong>
    </p>
    <table style="width:100%;border-collapse:collapse;margin:0 0 20px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">
      <tr>
        <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:120px;">Data</td>
        <td style="padding:8px 12px;color:#111827;font-weight:500;">{data_evento_str}</td>
      </tr>
      {local_row}
    </table>
    <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:16px 20px;text-align:center;">
      <p style="color:#15803d;font-weight:600;font-size:1rem;margin:0 0 8px;">QR Code de Acesso em Anexo &#128206;</p>
      <p style="color:#166534;font-size:0.88rem;margin:0;">
        O arquivo <strong>qrcode.png</strong> est&#225; em anexo neste e-mail.<br/>
        Apresente-o na portaria para confirmar sua entrada.
      </p>
    </div>
    <p style="color:#9ca3af;font-size:0.75rem;text-align:center;margin:16px 0 0;">
      Este QR code &#233; pessoal e intransfer&#237;vel.
    </p>
  </div>
  <div style="background:#f9fafb;padding:10px 24px;border-top:1px solid #e5e7eb;text-align:center;">
    <p style="color:#9ca3af;font-size:0.75rem;margin:0;">{condominio_nome}</p>
    {endereco_footer}
  </div>
</div>"""

        resend.api_key = api_key
        resend.Emails.send(
            {
                "from": email_from,
                "to": [convidado.email],
                "subject": f"Seu convite para {lista.titulo}",
                "html": html_body,
                "attachments": [
                    {
                        "filename": "qrcode.png",
                        "content": qr_bytes,
                    }
                ],
            }
        )
        return True
    except Exception:
        return False


def _is_sindico_ou_portaria(user):
    return (
        user.is_staff
        or user.groups.filter(name="Síndicos").exists()
        or user.groups.filter(name="Portaria").exists()
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def listas_convidados_view(request):
    """
    GET  — Morador vê suas próprias listas.
           Síndico/Portaria veem todas.
    POST — Morador cria uma nova lista.
    """
    user = request.user

    if request.method == "GET":
        search = request.query_params.get("search", "").strip()
        if _is_sindico_ou_portaria(user):
            qs = (
                ListaConvidados.objects.all()
                .prefetch_related("convidados")
                .order_by("-created_on")
            )
        elif _is_morador(user):
            qs = (
                ListaConvidados.objects.filter(morador=user)
                .prefetch_related("convidados")
                .order_by("-created_on")
            )
        else:
            return Response(
                {"error": "Sem permissão."}, status=status.HTTP_403_FORBIDDEN
            )

        if search:
            qs = qs.filter(titulo__icontains=search)

        data_evento = request.query_params.get("data_evento", "").strip()
        if data_evento:
            qs = qs.filter(data_evento=data_evento)

        serializer = ListaConvidadosSerializer(qs, many=True)
        return Response(serializer.data)

    # POST — apenas moradores criam listas
    if not _is_morador(user):
        return Response(
            {"error": "Apenas moradores podem criar listas de convidados."},
            status=status.HTTP_403_FORBIDDEN,
        )

    titulo = str(request.data.get("titulo", "")).strip()
    if not titulo:
        return Response(
            {"error": "Título é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    local_tipo = str(request.data.get("local_tipo", "")).strip()
    espaco_id = request.data.get("espaco") or None
    unidade_evento_id = request.data.get("unidade_evento") or None

    # Validação de local
    if local_tipo == "espaco" and not espaco_id:
        return Response(
            {"error": "Selecione o espaço do condomínio."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if local_tipo == "unidade" and not unidade_evento_id:
        return Response(
            {"error": "Selecione a unidade do evento."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lista = ListaConvidados.objects.create(
        morador=user,
        titulo=titulo,
        descricao=str(request.data.get("descricao", "")).strip(),
        data_evento=request.data.get("data_evento") or None,
        ativa=request.data.get("ativa", True),
        local_tipo=local_tipo,
        espaco_id=espaco_id,
        unidade_evento_id=unidade_evento_id,
    )

    # Criação em bulk de convidados (opcional)
    convidados_raw = request.data.get("convidados", [])
    if convidados_raw and isinstance(convidados_raw, list):
        seen_cpfs = set()
        for item in convidados_raw:
            cpf_digits = "".join(
                c for c in str(item.get("cpf", "")) if c.isdigit()
            )
            nome = str(item.get("nome", "")).strip()
            email = str(item.get("email", "")).strip()
            if len(cpf_digits) == 11 and nome and cpf_digits not in seen_cpfs:
                seen_cpfs.add(cpf_digits)
                convidado_criado = ConvidadoLista.objects.create(
                    lista=lista, cpf=cpf_digits, nome=nome, email=email
                )
                _enviar_qrcode_email(convidado_criado, lista)

    serializer = ListaConvidadosSerializer(lista)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def lista_convidados_detail_view(request, lista_pk):
    """
    GET    — detalhe de uma lista (morador dono ou síndico/portaria).
    PATCH  — morador atualiza título/descricao/data_evento/ativa.
    DELETE — morador exclui a lista.
    """
    user = request.user
    try:
        lista = ListaConvidados.objects.get(pk=lista_pk)
    except ListaConvidados.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Permissão de leitura: dono ou síndico/portaria
    pode_ler = (lista.morador == user) or _is_sindico_ou_portaria(user)
    # Permissão de escrita: apenas o dono
    pode_escrever = lista.morador == user

    if request.method == "GET":
        if not pode_ler:
            return Response(
                {"error": "Sem permissão."}, status=status.HTTP_403_FORBIDDEN
            )
        serializer = ListaConvidadosSerializer(lista)
        return Response(serializer.data)

    if request.method == "PATCH":
        if not pode_escrever:
            return Response(
                {"error": "Sem permissão."}, status=status.HTTP_403_FORBIDDEN
            )
        for field in (
            "titulo",
            "descricao",
            "data_evento",
            "ativa",
            "local_tipo",
        ):
            if field in request.data:
                value = request.data[field]
                if field == "data_evento":
                    value = value or None
                setattr(lista, field, value)
        if "espaco" in request.data:
            lista.espaco_id = request.data["espaco"] or None
        if "unidade_evento" in request.data:
            lista.unidade_evento_id = request.data["unidade_evento"] or None
        lista.save()
        serializer = ListaConvidadosSerializer(lista)
        return Response(serializer.data)

    if request.method == "DELETE":
        if not pode_escrever:
            return Response(
                {"error": "Sem permissão."}, status=status.HTTP_403_FORBIDDEN
            )
        lista.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def buscar_cpf_view(request, lista_pk):
    """
    POST { "cpf": "12345678901" }
    Tenta resolver o nome via BrasilAPI.
    Retorna {"cpf": "...", "nome": "...", "encontrado": true/false}.
    """
    user = request.user
    try:
        lista = ListaConvidados.objects.get(pk=lista_pk, morador=user)
    except ListaConvidados.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    cpf_raw = request.data.get("cpf", "")
    cpf_digits = "".join(c for c in str(cpf_raw) if c.isdigit())

    if len(cpf_digits) != 11:
        return Response(
            {"error": "CPF deve ter 11 dígitos."},
            status=status.HTTP_400_BAD_REQUEST,
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
        {"cpf": cpf_digits, "nome": nome, "encontrado": bool(nome)}
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def adicionar_convidado_view(request, lista_pk):
    """
    POST { "cpf": "12345678901", "nome": "João Silva" }
    Adiciona um convidado à lista do morador.
    """
    user = request.user
    try:
        lista = ListaConvidados.objects.get(pk=lista_pk, morador=user)
    except ListaConvidados.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    cpf_raw = request.data.get("cpf", "")
    cpf_digits = "".join(c for c in str(cpf_raw) if c.isdigit())
    nome = str(request.data.get("nome", "")).strip()

    if len(cpf_digits) != 11:
        return Response(
            {"error": "CPF deve ter 11 dígitos numéricos."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not nome:
        return Response(
            {"error": "Nome do convidado é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if ConvidadoLista.objects.filter(lista=lista, cpf=cpf_digits).exists():
        return Response(
            {"error": "Este CPF já está na lista."},
            status=status.HTTP_409_CONFLICT,
        )

    email = str(request.data.get("email", "")).strip()
    convidado = ConvidadoLista.objects.create(
        lista=lista, cpf=cpf_digits, nome=nome, email=email
    )
    _enviar_qrcode_email(convidado, lista)
    serializer = ConvidadoListaSerializer(convidado)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remover_convidado_view(request, lista_pk, convidado_pk):
    """
    DELETE — remove um convidado da lista. Apenas o dono da lista pode remover.
    """
    user = request.user
    try:
        lista = ListaConvidados.objects.get(pk=lista_pk, morador=user)
    except ListaConvidados.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        convidado = ConvidadoLista.objects.get(pk=convidado_pk, lista=lista)
    except ConvidadoLista.DoesNotExist:
        return Response(
            {"error": "Convidado não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    convidado.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def buscar_cpf_simples_view(request):
    """
    GET ?cpf=12345678901
    Busca nome pelo CPF: primeiro na base de usuários do sistema,
    depois tenta BrasilAPI como fallback.
    Retorna {"cpf": "...", "nome": "...", "encontrado": true/false}.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    cpf_raw = request.query_params.get("cpf", "")
    cpf_digits = "".join(c for c in str(cpf_raw) if c.isdigit())

    if len(cpf_digits) != 11:
        return Response(
            {"error": "CPF deve ter 11 dígitos."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 1. Buscar na base interna de usuários
    cpf_formatado = f"{cpf_digits[:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-{cpf_digits[9:]}"
    usuario = (
        User.objects.filter(cpf=cpf_formatado).first()
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

    # 1.5. Buscar em convidados de listas anteriores do morador logado
    convidado_anterior = (
        ConvidadoLista.objects.filter(
            cpf=cpf_digits, lista__morador=request.user
        )
        .order_by("-id")
        .first()
    )
    if convidado_anterior:
        return Response(
            {
                "cpf": cpf_digits,
                "nome": convidado_anterior.nome,
                "email": convidado_anterior.email,
                "encontrado": True,
                "fonte": "lista_anterior",
            }
        )

    # 2. Fallback: BrasilAPI
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
def convidados_anteriores_view(request):
    """
    GET ?q=texto — retorna convidados únicos (por CPF, mais recente) de listas
    anteriores do morador logado. Suporta busca por nome ou CPF.
    """
    from django.db.models import Max

    user = request.user
    q = request.query_params.get("q", "").strip()

    qs = ConvidadoLista.objects.filter(lista__morador=user)
    if q:
        cpf_q = "".join(c for c in q if c.isdigit())
        if cpf_q:
            qs = qs.filter(cpf__icontains=cpf_q)
        else:
            qs = qs.filter(nome__icontains=q)

    # Deduplica: pega o ID mais recente para cada CPF
    latest_ids = (
        qs.values("cpf")
        .annotate(latest_id=Max("id"))
        .values_list("latest_id", flat=True)
    )
    results = ConvidadoLista.objects.filter(id__in=latest_ids).order_by(
        "nome"
    )[:30]

    def fmt_cpf(cpf):
        if len(cpf) == 11:
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf

    data = [
        {
            "cpf": c.cpf,
            "cpf_formatado": fmt_cpf(c.cpf),
            "nome": c.nome,
            "email": c.email,
        }
        for c in results
    ]
    return Response(data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def atualizar_convidado_view(request, lista_pk, convidado_pk):
    """
    PATCH { "cpf": "12345678901", "nome": "Novo Nome" }
    Atualiza CPF e/ou nome de um convidado. Apenas o dono da lista.
    """
    user = request.user
    try:
        lista = ListaConvidados.objects.get(pk=lista_pk, morador=user)
    except ListaConvidados.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        convidado = ConvidadoLista.objects.get(pk=convidado_pk, lista=lista)
    except ConvidadoLista.DoesNotExist:
        return Response(
            {"error": "Convidado não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    new_cpf_raw = request.data.get("cpf")
    new_nome = request.data.get("nome")

    if new_cpf_raw is not None:
        cpf_digits = "".join(c for c in str(new_cpf_raw) if c.isdigit())
        if len(cpf_digits) != 11:
            return Response(
                {"error": "CPF deve ter 11 dígitos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            ConvidadoLista.objects.filter(lista=lista, cpf=cpf_digits)
            .exclude(pk=convidado_pk)
            .exists()
        ):
            return Response(
                {"error": "Este CPF já está na lista."},
                status=status.HTTP_409_CONFLICT,
            )
        convidado.cpf = cpf_digits

    if new_nome is not None:
        nome_stripped = str(new_nome).strip()
        if not nome_stripped:
            return Response(
                {"error": "Nome não pode ser vazio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        convidado.nome = nome_stripped

    if "email" in request.data:
        convidado.email = str(request.data["email"]).strip()

    convidado.save()
    serializer = ConvidadoListaSerializer(convidado)
    return Response(serializer.data)


# ── Novos endpoints: confirmação de entrada e QR Code ──────────────────────


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def confirmar_entrada_view(request, lista_pk, convidado_pk):
    """
    PATCH — toggle de entrada do convidado. Apenas portaria ou síndico.
    """
    if not _is_sindico_ou_portaria(request.user):
        return Response(
            {"error": "Sem permissão."}, status=status.HTTP_403_FORBIDDEN
        )

    try:
        lista = ListaConvidados.objects.get(pk=lista_pk)
    except ListaConvidados.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        convidado = ConvidadoLista.objects.get(pk=convidado_pk, lista=lista)
    except ConvidadoLista.DoesNotExist:
        return Response(
            {"error": "Convidado não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    from django.utils import timezone

    if convidado.entrada_confirmada:
        convidado.entrada_confirmada = False
        convidado.entrada_em = None
    else:
        convidado.entrada_confirmada = True
        convidado.entrada_em = timezone.now()
    convidado.save()

    serializer = ConvidadoListaSerializer(convidado)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def enviar_qrcode_view(request, lista_pk, convidado_pk):
    """
    POST — reenvia QR code por e-mail ao convidado. Apenas o morador dono da lista.
    """
    user = request.user
    try:
        lista = ListaConvidados.objects.select_related("morador").get(
            pk=lista_pk, morador=user
        )
    except ListaConvidados.DoesNotExist:
        return Response(
            {"error": "Lista não encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        convidado = ConvidadoLista.objects.get(pk=convidado_pk, lista=lista)
    except ConvidadoLista.DoesNotExist:
        return Response(
            {"error": "Convidado não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not convidado.email:
        return Response(
            {"error": "O convidado não tem e-mail cadastrado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from django.conf import settings as django_settings

    if not django_settings.RESEND_API_KEY:
        return Response(
            {"error": "Serviço de e-mail não configurado."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    enviado = _enviar_qrcode_email(convidado, lista)
    if not enviado:
        return Response(
            {"error": "Falha ao enviar e-mail."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(
        {"success": True, "message": "QR code enviado com sucesso."}
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirmar_por_qrcode_view(request):
    """
    POST { "token": "uuid" } — confirma entrada pelo QR code. Apenas portaria ou síndico.
    """
    if not _is_sindico_ou_portaria(request.user):
        return Response(
            {"error": "Sem permissão."}, status=status.HTTP_403_FORBIDDEN
        )

    token = str(request.data.get("token", "")).strip()
    if not token:
        return Response(
            {"error": "Token é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        convidado = ConvidadoLista.objects.select_related(
            "lista", "lista__morador"
        ).get(qr_token=token)
    except ConvidadoLista.DoesNotExist:
        return Response(
            {"error": "QR code inválido."}, status=status.HTTP_404_NOT_FOUND
        )
    except Exception:
        return Response(
            {"error": "QR code inválido."}, status=status.HTTP_400_BAD_REQUEST
        )

    from django.utils import timezone

    lista = convidado.lista
    morador_nome = (
        getattr(lista.morador, "full_name", None)
        or lista.morador.get_full_name()
        or lista.morador.username
    )

    if convidado.entrada_confirmada:
        return Response(
            {
                "aviso": "Convidado já confirmou a entrada anteriormente.",
                "nome": convidado.nome,
                "lista": lista.titulo,
                "morador_nome": morador_nome,
            }
        )

    convidado.entrada_confirmada = True
    convidado.entrada_em = timezone.now()
    convidado.save()

    return Response(
        {
            "success": True,
            "nome": convidado.nome,
            "lista": lista.titulo,
            "morador_nome": morador_nome,
        }
    )
