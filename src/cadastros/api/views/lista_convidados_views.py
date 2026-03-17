import json
import urllib.error
import urllib.request

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import ConvidadoLista, ListaConvidados, Visitante
from ..serializers.lista_convidados_serializer import (
    ConvidadoListaSerializer,
    ListaConvidadosSerializer,
)


def _is_morador(user):
    return user.groups.filter(name="Moradores").exists()


def _pode_criar_lista(user):
    return user.groups.filter(name__in=["Moradores", "Síndicos"]).exists()


def _enviar_qrcode_email(convidado, lista):
    """
    Envia o QR code de acesso por e-mail ao convidado.
    Silencioso em caso de erro — não bloqueia o fluxo principal.
    Retorna True se enviado com sucesso.
    """
    import base64
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
            # Se tivermos apenas o CEP armazenado, consultar ViaCEP para obter o
            # endereço completo e montar uma descrição amigável.
            cep_raw = (condominio.cep or "").strip()
            endereco_parts = []
            if cep_raw:
                cep_only = "".join(c for c in cep_raw if c.isdigit())
                if cep_only:
                    try:
                        via_url = f"https://viacep.com.br/ws/{cep_only}/json/"
                        req = urllib.request.Request(
                            via_url, headers={"User-Agent": "CancellaFlow/1.0"}
                        )
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            data = json.load(resp)
                        # Se ViaCEP indicar erro, não usar
                        if data.get("erro"):
                            raise ValueError("CEP não encontrado no ViaCEP")
                        # data pode conter: logradouro, bairro, localidade, uf
                        log = data.get("logradouro") or ""
                        bairro = data.get("bairro") or ""
                        cidade = data.get("localidade") or ""
                        uf = data.get("uf") or ""
                        if log:
                            endereco_parts.append(log)
                        if bairro:
                            endereco_parts.append(bairro)
                        if cidade or uf:
                            cidade_uf = ", ".join(p for p in [cidade, uf] if p)
                            endereco_parts.append(cidade_uf)
                        # manter o CEP por último
                        endereco_parts.append(f"CEP {cep_raw}")
                    except Exception:
                        # Se a consulta falhar, fallback para os dados básicos
                        endereco_parts = []
                        if condominio.cep:
                            endereco_parts.append(f"CEP {condominio.cep}")
            # adicionar número e complemento se existirem — colocados após o logradouro
            numero_comp = []
            if getattr(condominio, "numero", None):
                numero_comp.append(f"n° {condominio.numero}")
            if getattr(condominio, "complemento", None):
                numero_comp.append(condominio.complemento)
            if numero_comp:
                endereco_parts.extend(numero_comp)

            condominio_endereco = (
                ", ".join(endereco_parts) if endereco_parts else ""
            )

        local_descricao = ListaConvidadosSerializer().get_local_descricao(
            lista
        )

        # Gerar QR code em memória: manter bytes e também base64 para fallback
        img = qrcode.make(str(convidado.qr_token))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_bytes = buffer.getvalue()
        qr_bytes_list = list(qr_bytes)
        qr_base64 = base64.b64encode(qr_bytes).decode()

        # Tentar obter logo do condomínio — prioriza armazenamento em DB, fallback no FileField
        logo_html = ""
        logo_email_bytes = None
        logo_filename = "logo.png"
        try:
            from PIL import Image

            raw_logo_bytes = None
            # 1) Preferir logo armazenada diretamente no banco
            if condominio and getattr(condominio, "logo_db_data", None):
                raw_logo_bytes = bytes(condominio.logo_db_data)
                logo_filename = condominio.logo_db_filename or "logo.png"
            # 2) Fallback: FileField
            elif condominio and getattr(condominio, "logo", None):
                logo_field = condominio.logo
                try:
                    logo_field.open("rb")
                    raw_logo_bytes = logo_field.read()
                    logo_field.close()
                    logo_filename = (
                        logo_field.name.split("/")[-1]
                        if logo_field.name
                        else "logo.png"
                    )
                except Exception:
                    raw_logo_bytes = None

            if raw_logo_bytes:
                # Redimensionar para caber em max 220 × 80 px mantendo proporção
                img_buf = io.BytesIO(raw_logo_bytes)
                img = Image.open(img_buf).convert("RGBA")
                img.thumbnail((220, 80), Image.LANCZOS)
                out_buf = io.BytesIO()
                img.save(out_buf, format="PNG")  # PNG preserva transparência
                logo_email_bytes = out_buf.getvalue()
                logo_html = f'<img src="cid:logo" alt="{condominio_nome}" style="max-width:220px;max-height:80px;margin-top:8px;" />'
        except Exception:
            logo_html = ""
            logo_email_bytes = None

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

        endereco_row = ""
        if condominio_endereco:
            endereco_row = (
                "<tr>"
                '<td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:120px;">Endereço</td>'
                f'<td style="padding:8px 12px;color:#111827;font-weight:500;">{condominio_endereco}</td></tr>'
            )

        html_body = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
  <div style="background:#19294a;padding:20px 24px;text-align:center;">
    <p style="color:#ffffff;margin:0;font-size:1rem;font-weight:600;">{condominio_nome}</p>
    {logo_html}
  </div>
  <div style="padding:24px;background:#ffffff;">
    <h2 style="color:#19294a;margin:0 0 12px;font-size:1.1rem;">Olá, {convidado.nome}!</h2>
    <p style="color:#374151;line-height:1.6;margin:0 0 16px;">
      Você foi convidado(a) por <strong>{morador_nome}</strong> para:<br/>
      <strong style="font-size:1.05rem;color:#2abb98;">{lista.titulo}</strong>
    </p>
    <table style="width:100%;border-collapse:collapse;margin:0 0 20px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">
      <tr>
        <td style="padding:8px 12px;color:#6b7280;font-size:0.88rem;width:120px;">Data</td>
        <td style="padding:8px 12px;color:#111827;font-weight:500;">{data_evento_str}</td>
      </tr>
      {local_row}
      {endereco_row}
    </table>
    <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:16px 20px;text-align:center;">
      <p style="color:#15803d;font-weight:600;font-size:1rem;margin:0 0 8px;">QR Code de Acesso</p>
      <p style="color:#166534;font-size:0.88rem;margin:0 0 12px;">Apresente-o na portaria para confirmar sua entrada.</p>
        <div style="display:flex;justify-content:center;align-items:center;">
            <img src="cid:qrcode" alt="QR Code de Acesso" style="width:200px;height:200px;border-radius:8px;" />
        </div>
    </div>
    <p style="color:#9ca3af;font-size:0.75rem;text-align:center;margin:16px 0 0;">Este QR code é pessoal e intransferível.</p>
  </div>
  <div style="background:#f9fafb;padding:10px 24px;border-top:1px solid #e5e7eb;text-align:center;">
    <p style="color:#9ca3af;font-size:0.75rem;margin:0;">{condominio_nome}</p>
  </div>
</div>"""

        resend.api_key = api_key
        payload = {
            "from": email_from,
            "to": [convidado.email],
            "subject": f"Seu convite para {lista.titulo}",
            "html": html_body,
            "attachments": [
                {
                    "filename": "qrcode.png",
                    "content": base64.b64encode(qr_bytes).decode(),
                    "content_id": "qrcode",
                    "disposition": "inline",
                }
            ],
        }

        # Incluir logo redimensionada como anexo inline se disponível
        if logo_email_bytes:
            payload["attachments"].append(
                {
                    "filename": "logo.png",
                    "content": base64.b64encode(logo_email_bytes).decode(),
                    "content_id": "logo",
                    "disposition": "inline",
                }
            )

        resend.Emails.send(payload)
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
                ListaConvidados.objects.filter(
                    morador__condominio=user.condominio
                )
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

    # POST — moradores e síndicos podem criar listas
    if not _pode_criar_lista(user):
        return Response(
            {
                "error": "Apenas moradores ou síndicos podem criar listas de convidados."
            },
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

    # Permissão de leitura: dono ou síndico/portaria do mesmo condomínio
    mesmo_condominio = (
        _is_sindico_ou_portaria(user)
        and lista.morador.condominio_id == user.condominio_id
    )
    pode_ler = (lista.morador == user) or mesmo_condominio
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
        # Tentar como token de visitante
        try:
            import uuid as _uuid

            visitante = Visitante.objects.select_related("morador").get(
                qr_token=token
            )
        except (Visitante.DoesNotExist, Exception):
            return Response(
                {"error": "QR code inválido."},
                status=status.HTTP_404_NOT_FOUND,
            )

        from django.utils import timezone as tz

        morador_nome = (
            getattr(visitante.morador, "full_name", None)
            or visitante.morador.get_full_name()
            or visitante.morador.username
        )

        # Invalidar token após uso (exceto visitante permanente)
        if not visitante.is_permanente:
            visitante.qr_token = _uuid.uuid4()
            visitante.save(update_fields=["qr_token"])

        resp = {
            "success": True,
            "nome": visitante.nome,
            "lista": "Visitante",
            "morador_nome": morador_nome,
            "is_visitante": True,
            "is_permanente": visitante.is_permanente,
            "documento": visitante.documento,
        }
        # Se o documento parecer um CPF com 11 dígitos, retorne também como cpf (somente dígitos)
        digitos = "".join(
            c for c in str(visitante.documento or "") if c.isdigit()
        )
        if len(digitos) == 11:
            resp["cpf"] = digitos

        return Response(resp)
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
            "lista": lista.titulo,
            "morador_nome": morador_nome,
            "cpf": convidado.cpf,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_qrcode_view(request):
    """
    GET ?token=<uuid> — Retorna um PNG do QR Code com o nome da pessoa abaixo.
    Busca o token em ConvidadoLista e depois em Visitante.
    """
    import io

    import qrcode
    from django.http import HttpResponse
    from PIL import Image, ImageDraw, ImageFont

    token = request.query_params.get("token", "").strip()
    if not token:
        return Response(
            {"error": "Token é obrigatório."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    nome = None
    try:
        convidado = ConvidadoLista.objects.get(qr_token=token)
        nome = convidado.nome
    except ConvidadoLista.DoesNotExist:
        pass

    if nome is None:
        try:
            visitante = Visitante.objects.get(qr_token=token)
            nome = visitante.nome
        except Visitante.DoesNotExist:
            return Response(
                {"error": "QR code não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

    # Gerar QR code
    qr_img = qrcode.make(str(token))
    qr_size = qr_img.size[0]

    # Canvas: QR + padding + faixa com o nome
    padding = 20
    name_height = 44
    canvas = Image.new(
        "RGB",
        (qr_size + padding * 2, qr_size + padding * 2 + name_height),
        "white",
    )
    canvas.paste(qr_img, (padding, padding))

    draw = ImageDraw.Draw(canvas)
    font = None
    for font_path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        try:
            font = ImageFont.truetype(font_path, 18)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    text_x = canvas.width // 2
    text_y = qr_size + padding + name_height // 2
    try:
        draw.text(
            (text_x, text_y), nome, fill="#111827", font=font, anchor="mm"
        )
    except TypeError:
        try:
            bbox = draw.textbbox((0, 0), nome, font=font)
            text_w = bbox[2] - bbox[0]
        except AttributeError:
            text_w = len(nome) * 10
        draw.text(
            (text_x - text_w // 2, text_y - 9), nome, fill="#111827", font=font
        )

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    output.seek(0)

    safe_nome = "".join(
        c if c.isalnum() or c in "-_" else "-"
        for c in nome.lower().replace(" ", "-")
    )
    response = HttpResponse(output.read(), content_type="image/png")
    response["Content-Disposition"] = (
        f'attachment; filename="qrcode-{safe_nome}.png"'
    )
    return response
