from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class GroupListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Verificar se o usuário tem permissão (apenas staff ou admin)
        if (
            not request.user.is_staff
            and not request.user.groups.filter(name="admin").exists()
        ):
            return Response(
                {"error": "Acesso negado"}, status=status.HTTP_403_FORBIDDEN
            )

        try:
            # Buscar parâmetros
            page = int(request.GET.get("page", 1))
            search = request.GET.get("search", "")
            page_size = int(request.GET.get("page_size", 10))

            # Filtrar grupos
            groups = Group.objects.all().order_by("name")

            if search:
                groups = groups.filter(name__icontains=search)

            # Paginação
            paginator = Paginator(groups, page_size)
            page_obj = paginator.get_page(page)

            # Serializar dados
            groups_data = []
            for group in page_obj:
                groups_data.append(
                    {
                        "id": group.id,
                        "nome": group.name,
                        "is_ativo": True,  # Grupos do Django são sempre ativos
                        "users_count": group.user_set.count(),
                    }
                )

            return Response(
                {
                    "results": groups_data,
                    "count": paginator.count,
                    "num_pages": paginator.num_pages,
                    "current_page": page,
                    "page_size": page_size,
                }
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        # Verificar se o usuário tem permissão (apenas staff ou admin)
        if (
            not request.user.is_staff
            and not request.user.groups.filter(name="admin").exists()
        ):
            return Response(
                {"error": "Acesso negado"}, status=status.HTTP_403_FORBIDDEN
            )

        try:
            nome = request.data.get("nome")

            if not nome:
                return Response(
                    {"error": "Nome é obrigatório"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Verificar se já existe
            if Group.objects.filter(name=nome).exists():
                return Response(
                    {"error": "Já existe um grupo com este nome"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Criar grupo
            group = Group.objects.create(name=nome)

            return Response(
                {
                    "id": group.id,
                    "nome": group.name,
                    "message": "Grupo criado com sucesso",
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GroupDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, group_id):
        # Verificar se o usuário tem permissão (apenas staff ou admin)
        if (
            not request.user.is_staff
            and not request.user.groups.filter(name="admin").exists()
        ):
            return Response(
                {"error": "Acesso negado"}, status=status.HTTP_403_FORBIDDEN
            )

        try:
            group = Group.objects.get(id=group_id)

            nome = request.data.get("nome")
            if nome and nome != group.name:
                # Verificar se já existe outro grupo com este nome
                if (
                    Group.objects.filter(name=nome)
                    .exclude(id=group_id)
                    .exists()
                ):
                    return Response(
                        {"error": "Já existe um grupo com este nome"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                group.name = nome
                group.save()

            return Response({"message": "Grupo atualizado com sucesso"})

        except Group.DoesNotExist:
            return Response(
                {"error": "Grupo não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, group_id):
        # Verificar se o usuário tem permissão (apenas staff ou admin)
        if (
            not request.user.is_staff
            and not request.user.groups.filter(name="admin").exists()
        ):
            return Response(
                {"error": "Acesso negado"}, status=status.HTTP_403_FORBIDDEN
            )

        try:
            group = Group.objects.get(id=group_id)

            # Verificar se há usuários associados
            if group.user_set.exists():
                return Response(
                    {
                        "error": "Não é possível excluir um grupo que possui usuários associados"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            group.delete()
            return Response({"message": "Grupo excluído com sucesso"})

        except Group.DoesNotExist:
            return Response(
                {"error": "Grupo não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
