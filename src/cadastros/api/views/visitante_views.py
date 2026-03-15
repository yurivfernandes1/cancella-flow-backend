from django.core.paginator import Paginator
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Visitante
from ..serializers import VisitanteListSerializer, VisitanteSerializer


def _enviar_qrcode_email_visitante(visitante):
    """
    Envia o QR code de acesso por e-mail ao visitante.
    Silencioso em caso de erro — não bloqueia o fluxo principal.
    Retorna True se enviado com sucesso.
    """
    import base64
    import io
    import json
    import urllib.error
    import urllib.request

    import qrcode
    import resend
    from django.conf import settings as django_settings

    if not visitante.email:
        return False

    api_key = django_settings.RESEND_API_KEY
    email_from = django_settings.EMAIL_FROM
    if not api_key:
        return False

    try:
        morador = visitante.morador
        condominio = getattr(morador, "condominio", None)
        condominio_nome = condominio.nome if condominio else "Condomínio"

        # Resolver endereço via ViaCEP
        condominio_endereco = ""
        if condominio:
            cep_raw = (getattr(condominio, "cep", None) or "").strip()
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
                        if not data.get("erro"):
                            for part in [data.get("logradouro"), data.get("bairro")]:
                                if part:
                                    endereco_parts.append(part)
                            cidade_uf = ", ".join(p for p in [data.get("localidade"), data.get("uf")] if p)
                            if cidade_uf:
                                endereco_parts.append(cidade_uf)
                            endereco_parts.append(f"CEP {cep_raw}")
                    except Exception:
                        if cep_raw:
                            endereco_parts.append(f"CEP {cep_raw}")
            for attr in ["numero", "complemento"]:
                val = getattr(condominio, attr, None)
                if val:
                    endereco_parts.append(str(val))
            condominio_endereco = ", ".join(endereco_parts) if endereco_parts else ""

        morador_nome = (
            getattr(morador, "full_name", None)
            or morador.get_full_name()
            or morador.username
        )

        # Gerar QR code em memória
        img = qrcode.make(str(visitante.qr_token))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_bytes = buffer.getvalue()

        # Logo do condomínio (opcional)
        logo_html = ""
        logo_email_bytes = None
        try:
            from PIL import Image

            raw_logo_bytes = None
            if condominio and getattr(condominio, "logo_db_data", None):
                raw_logo_bytes = bytes(condominio.logo_db_data)
            elif condominio and getattr(condominio, "logo", None):
                logo_field = condominio.logo
                try:
                    logo_field.open("rb")
                    raw_logo_bytes = logo_field.read()
                    logo_field.close()
                except Exception:
                    raw_logo_bytes = None
            if raw_logo_bytes:
                img_buf = io.BytesIO(raw_logo_bytes)
                pil_img = Image.open(img_buf).convert("RGBA")
                pil_img.thumbnail((220, 80), Image.LANCZOS)
                out_buf = io.BytesIO()
                pil_img.save(out_buf, format="PNG")
                logo_email_bytes = out_buf.getvalue()
                logo_html = f'<img src="cid:logo" alt="{condominio_nome}" style="max-width:220px;max-height:80px;margin-top:8px;" />'
        except Exception:
            logo_html = ""
            logo_email_bytes = None

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
    <h2 style="color:#19294a;margin:0 0 12px;font-size:1.1rem;">Olá, {visitante.nome}!</h2>
    <p style="color:#374151;line-height:1.6;margin:0 0 16px;">
      <strong>{morador_nome}</strong> registrou sua visita ao condomínio.<br/>
      Apresente o QR Code abaixo na portaria para confirmar sua entrada.
    </p>
    {f'<table style="width:100%;border-collapse:collapse;margin:0 0 20px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">{endereco_row}</table>' if endereco_row else ''}
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
            "to": [visitante.email],
            "subject": f"Seu QR Code de Acesso — {condominio_nome}",
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def visitante_enviar_qrcode_view(request, pk):
    """
    POST — Envia o QR code de acesso por e-mail ao visitante.
    Apenas o morador dono ou admin pode enviar.
    """
    user = request.user
    try:
        visitante = Visitante.objects.get(pk=pk)
    except Visitante.DoesNotExist:
        return Response(
            {"error": "Visitante não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    is_morador = user.groups.filter(name="Moradores").exists()
    if not (user.is_staff or (is_morador and visitante.morador == user)):
        return Response({"error": "Sem permissão."}, status=status.HTTP_403_FORBIDDEN)

    if not visitante.email:
        return Response(
            {"error": "O visitante não possui e-mail cadastrado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    enviado = _enviar_qrcode_email_visitante(visitante)
    if enviado:
        return Response({"success": True, "message": "QR code enviado com sucesso."})
    return Response(
        {"error": "Falha ao enviar o e-mail. Verifique as configurações do servidor."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
