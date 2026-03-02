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

    lista = ListaConvidados.objects.create(
        morador=user,
        titulo=titulo,
        descricao=str(request.data.get("descricao", "")).strip(),
        data_evento=request.data.get("data_evento") or None,
        ativa=request.data.get("ativa", True),
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
            if len(cpf_digits) == 11 and nome and cpf_digits not in seen_cpfs:
                seen_cpfs.add(cpf_digits)
                ConvidadoLista.objects.create(
                    lista=lista, cpf=cpf_digits, nome=nome
                )

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
        for field in ("titulo", "descricao", "data_evento", "ativa"):
            if field in request.data:
                value = request.data[field]
                if field == "data_evento":
                    value = value or None
                setattr(lista, field, value)
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
            url, headers={"User-Agent": "CanellaFlow/1.0"}
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

    convidado = ConvidadoLista.objects.create(
        lista=lista, cpf=cpf_digits, nome=nome
    )
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
        return Response({"cpf": cpf_digits, "nome": nome, "encontrado": True})

    # 2. Fallback: BrasilAPI
    nome = None
    try:
        url = f"https://brasilapi.com.br/api/cpf/v1/{cpf_digits}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "CanellaFlow/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            nome = data.get("nome") or data.get("name")
    except Exception:
        nome = None

    return Response(
        {"cpf": cpf_digits, "nome": nome, "encontrado": bool(nome)}
    )


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

    convidado.save()
    serializer = ConvidadoListaSerializer(convidado)
    return Response(serializer.data)
