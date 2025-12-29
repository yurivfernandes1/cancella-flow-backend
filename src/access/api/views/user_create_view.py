from cadastros.models import Condominio
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()


class UserCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Verificar permissões baseadas no tipo de usuário que está sendo criado
        user_type = request.data.get("user_type", "funcionario")

        # Administradores podem criar síndicos
        if user_type == "sindico":
            if not (
                request.user.is_staff
                or request.user.groups.filter(name="admin").exists()
            ):
                return Response(
                    {"error": "Apenas administradores podem criar síndicos"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Síndicos podem criar funcionários e moradores
        elif user_type in ["funcionario", "morador"]:
            if not (
                request.user.is_staff
                or request.user.groups.filter(name="admin").exists()
                or request.user.groups.filter(name="Síndicos").exists()
            ):
                return Response(
                    {"error": "Acesso negado para criar este tipo de usuário"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            # Determinar condomínio
            condominio = None
            if user_type == "sindico":
                condominio_id = request.data.get("condominio_id")
                if not condominio_id:
                    return Response(
                        {"error": "Condomínio é obrigatório para síndico"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                try:
                    condominio = Condominio.objects.get(id=condominio_id)
                except Condominio.DoesNotExist:
                    return Response(
                        {"error": "Condomínio não encontrado"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                # Funcionário/Morador: usar da requisição, senão o do usuário logado
                condominio_id = request.data.get("condominio_id") or (
                    request.user.condominio.id
                    if getattr(request.user, "condominio", None)
                    else None
                )
                if condominio_id:
                    try:
                        condominio = Condominio.objects.get(id=condominio_id)
                    except Condominio.DoesNotExist:
                        condominio = None

            # Obter unidade se fornecida
            from cadastros.models import Unidade

            unidade = None
            unidade_id = request.data.get("unidade_id")
            if unidade_id:
                try:
                    unidade = Unidade.objects.get(id=unidade_id)
                except Unidade.DoesNotExist:
                    return Response(
                        {"error": "Unidade não encontrada"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            with transaction.atomic():
                user = User.objects.create_user(
                    username=request.data.get("username", "").lower(),
                    password=request.data.get("password", "").strip(),
                    first_name=request.data.get("first_name", "").strip(),
                    last_name=request.data.get("last_name", "").strip(),
                    full_name=request.data.get("full_name", "").strip()
                    or f"{request.data.get('first_name', '').strip()} {request.data.get('last_name', '').strip()}",
                    email=request.data.get("email", "").strip(),
                    cpf=request.data.get("cpf", "").strip(),
                    phone=request.data.get("phone", "").strip(),
                    is_staff=request.data.get("is_staff", False),
                    is_active=True,
                    condominio=condominio,
                    unidade=unidade,
                    created_by=request.user,
                )

                # Associar ao grupo correto baseado no tipo
                # Se for 'sindico_morador', adicionar aos dois grupos
                group_names = []
                if user_type == "sindico_morador":
                    try:
                        sindico_group, _ = Group.objects.get_or_create(
                            name="Síndicos"
                        )
                        morador_group, _ = Group.objects.get_or_create(
                            name="Moradores"
                        )
                        user.groups.add(sindico_group, morador_group)
                        group_names = ["Síndicos", "Moradores"]
                    except Exception as e:
                        print(
                            f"Erro ao associar grupos para síndico_morador: {e}"
                        )
                else:
                    group_mapping = {
                        "sindico": "Síndicos",
                        "portaria": "Portaria",
                        "morador": "Moradores",
                    }

                    group_name = group_mapping.get(user_type)
                    if group_name:
                        try:
                            group, created = Group.objects.get_or_create(
                                name=group_name
                            )
                            user.groups.add(group)
                            group_names = [group_name]
                        except Exception as e:
                            print(f"Erro ao associar grupo {group_name}: {e}")

                user.save()

                return Response(
                    {
                        "message": f"{user_type.capitalize()} criado com sucesso",
                        "id": user.id,
                        "username": user.username,
                        "user_type": user_type,
                        "groups": group_names,
                        "condominio_id": user.condominio.id
                        if user.condominio
                        else None,
                    },
                    status=status.HTTP_201_CREATED,
                )

        except ValidationError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Erro ao criar usuário: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
