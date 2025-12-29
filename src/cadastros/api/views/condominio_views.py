from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import Condominio
from ..serializers import CondominioListSerializer, CondominioSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def condominio_list_view(request):
    """
    Lista todos os condomínios com paginação e busca
    """
    try:
        # Busca
        search = request.GET.get("search", "")
        condominios = Condominio.objects.all()

        if search:
            condominios = condominios.filter(
                Q(nome__icontains=search)
                | Q(cep__icontains=search)
                | Q(cnpj__icontains=search)
            )

        # Ordenação
        condominios = condominios.order_by("-created_at")

        # Paginação
        page = int(request.GET.get("page", 1))
        paginator = Paginator(condominios, 10)
        page_obj = paginator.get_page(page)

        serializer = CondominioListSerializer(
            page_obj.object_list, many=True, context={"request": request}
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
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Erro ao listar condomínios: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def condominio_create_view(request):
    """
    Cria um novo condomínio
    """
    try:
        # Verificar permissão
        if not (
            request.user.is_staff
            or request.user.groups.filter(name="admin").exists()
        ):
            return Response(
                {"error": "Você não tem permissão para criar condomínios."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Suportar tanto JSON quanto FormData (para upload de arquivos)
        serializer = CondominioSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            condominio = serializer.save()
            # Log para debug: verificar se o arquivo de logo foi recebido e salvo
            try:
                logo_path = condominio.logo.url if condominio.logo else None
            except Exception:
                logo_path = None
            print(
                f"[condominio_create_view] Condominio criado id={condominio.id}, logo={logo_path}"
            )
            return Response(
                CondominioSerializer(
                    condominio, context={"request": request}
                ).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Erro ao criar condomínio: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def condominio_detail_view(request, pk):
    """
    Obtém detalhes de um condomínio específico
    """
    try:
        condominio = Condominio.objects.get(pk=pk)
        serializer = CondominioSerializer(
            condominio, context={"request": request}
        )
        return Response(serializer.data)

    except Condominio.DoesNotExist:
        return Response(
            {"error": "Condomínio não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao obter condomínio: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def condominio_update_view(request, pk):
    """
    Atualiza um condomínio
    """
    try:
        # Verificar permissão
        if not (
            request.user.is_staff
            or request.user.groups.filter(name="admin").exists()
        ):
            return Response(
                {"error": "Você não tem permissão para editar condomínios."},
                status=status.HTTP_403_FORBIDDEN,
            )

        condominio = Condominio.objects.get(pk=pk)

        # Suportar tanto JSON quanto FormData (para upload de arquivos)
        serializer = CondominioSerializer(
            condominio,
            data=request.data,
            partial=(request.method == "PATCH"),
            context={"request": request},
        )

        if serializer.is_valid():
            condominio = serializer.save()
            # Log para debug: confirmar logo atualizada
            try:
                logo_path = condominio.logo.url if condominio.logo else None
            except Exception:
                logo_path = None
            print(
                f"[condominio_update_view] Condominio id={condominio.id} atualizado, logo={logo_path}"
            )
            return Response(
                CondominioSerializer(
                    condominio, context={"request": request}
                ).data
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Condominio.DoesNotExist:
        return Response(
            {"error": "Condomínio não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Erro ao atualizar condomínio: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def condominio_delete_view(request, pk):
    """
    Exclui um condomínio
    """
    try:
        # Verificar permissão
        if not (
            request.user.is_staff
            or request.user.groups.filter(name="admin").exists()
        ):
            return Response(
                {"error": "Você não tem permissão para excluir condomínios."},
                status=status.HTTP_403_FORBIDDEN,
            )

        condominio = Condominio.objects.get(pk=pk)
        condominio.delete()

        return Response(
            {"message": "Condomínio excluído com sucesso."},
            status=status.HTTP_204_NO_CONTENT,
        )

    except Condominio.DoesNotExist:
        return Response(
            {"error": "Condomínio não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": f"Erro ao excluir condomínio: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def condominio_options_view(request):
    """
    Lista todos os condomínios ativos para uso em selects (sem paginação)
    """
    try:
        condominios = Condominio.objects.filter(is_ativo=True).order_by("nome")

        # Retorna apenas id e nome para selects
        data = [
            {
                "id": condominio.id,
                "nome": condominio.nome,
                "label": condominio.nome,  # Para compatibilidade com react-select
            }
            for condominio in condominios
        ]

        return Response(data)

    except Exception as e:
        return Response(
            {"error": f"Erro ao listar opções de condomínios: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def condominio_logo_db_view(request, pk):
    """Serve a logo armazenada no banco como bytes (BLOB)."""
    try:
        condominio = Condominio.objects.get(pk=pk)
        if not condominio.logo_db_data:
            return Response(
                {"error": "Logo não encontrada no DB."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return HttpResponse(
            condominio.logo_db_data,
            content_type=condominio.logo_db_content_type
            or "application/octet-stream",
        )

    except Condominio.DoesNotExist:
        return Response(
            {"error": "Condomínio não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Erro ao servir logo do DB: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def condominio_upload_logo_db_view(request, pk):
    """Recebe upload multipart/form-data e salva bytes no modelo CondominioLogo."""
    try:
        # Permissão: somente staff ou admin
        if not (
            request.user.is_staff
            or request.user.groups.filter(name="admin").exists()
        ):
            return Response(
                {"error": "Você não tem permissão."},
                status=status.HTTP_403_FORBIDDEN,
            )

        condominio = Condominio.objects.get(pk=pk)

        # Arquivo deve vir em request.FILES['logo']
        arquivo = request.FILES.get("logo")
        if not arquivo:
            return Response(
                {"error": "Nenhum arquivo 'logo' enviado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ler conteúdo em bytes e salvar nos campos do condominio
        conteúdo = arquivo.read()
        condominio.logo_db_data = conteúdo
        condominio.logo_db_content_type = arquivo.content_type
        condominio.logo_db_filename = arquivo.name
        condominio.save()

        return Response({"message": "Logo salva no DB."})

    except Condominio.DoesNotExist:
        return Response(
            {"error": "Condomínio não encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Erro ao salvar logo no DB: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
