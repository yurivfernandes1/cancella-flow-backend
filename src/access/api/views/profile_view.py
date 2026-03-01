from app.utils.validators import format_cpf
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Buscar os grupos do usuário
        groups = user.groups.all().values("id", "name")

        return Response(
            {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.full_name,
                "email": user.email,
                "cpf": user.cpf,
                "phone": user.phone,
                "first_access": user.first_access,
                "is_staff": user.is_staff,
                "is_active": user.is_active,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "groups": list(groups),
                "condominio_id": user.condominio.id
                if user.condominio
                else None,
                "condominio_nome": user.condominio.nome
                if user.condominio
                else None,
                "unidade_id": user.unidade.id if user.unidade else None,
                "unidade_identificacao": user.unidade.identificacao_completa
                if user.unidade
                else None,
            }
        )

    def patch(self, request, user_id=None):
        try:
            # Determinar usuário alvo da atualização
            target_user = None

            if user_id is None:
                target_user = request.user
            else:
                # Se o id for do próprio usuário, sempre permitir
                if request.user.id == user_id:
                    target_user = request.user
                else:
                    # Staff pode editar qualquer usuário
                    if request.user.is_staff:
                        target_user = User.objects.get(id=user_id)
                    # Síndicos podem editar usuários do mesmo condomínio
                    elif request.user.groups.filter(name="Síndicos").exists():
                        candidate = User.objects.get(id=user_id)
                        if getattr(
                            request.user, "condominio_id", None
                        ) and request.user.condominio_id == getattr(
                            candidate, "condominio_id", None
                        ):
                            target_user = candidate
                        else:
                            return Response(
                                {
                                    "error": "Você não tem permissão para editar este usuário."
                                },
                                status=status.HTTP_403_FORBIDDEN,
                            )
                    else:
                        return Response(
                            {
                                "error": "Você não tem permissão para editar este usuário."
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )

            # Campo especial para senha
            if "password" in request.data:
                target_user.set_password(request.data["password"])

            # Atualiza outros campos
            allowed_fields = [
                "full_name",
                "first_name",
                "last_name",
                "username",
                "email",
                "cpf",
                "phone",
                "is_active",
                # "is_staff" somente para admin (verificado abaixo)
            ]

            for field in allowed_fields:
                if field in request.data:
                    setattr(target_user, field, request.data[field])

            # is_staff só pode ser alterado por staff
            if "is_staff" in request.data and request.user.is_staff:
                target_user.is_staff = bool(request.data["is_staff"])

            # Atualizar condomínio se fornecido
            if "condominio_id" in request.data:
                if request.data["condominio_id"]:
                    from cadastros.models import Condominio

                    try:
                        condominio = Condominio.objects.get(
                            id=request.data["condominio_id"]
                        )
                        target_user.condominio = condominio
                    except Condominio.DoesNotExist:
                        return Response(
                            {"error": "Condomínio não encontrado"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    target_user.condominio = None

            # Atualizar unidade se fornecida
            if "unidade_id" in request.data:
                if request.data["unidade_id"]:
                    from cadastros.models import Unidade

                    try:
                        unidade = Unidade.objects.get(
                            id=request.data["unidade_id"]
                        )
                        target_user.unidade = unidade
                    except Unidade.DoesNotExist:
                        return Response(
                            {"error": "Unidade não encontrada"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    target_user.unidade = None

            # Gerenciar grupo Moradores via campo is_morador
            if "is_morador" in request.data:
                from django.contrib.auth.models import Group

                try:
                    grupo_moradores = Group.objects.get(name="Moradores")
                    is_morador = bool(request.data["is_morador"])

                    if is_morador:
                        # Adicionar ao grupo Moradores se não estiver
                        if not target_user.groups.filter(
                            id=grupo_moradores.id
                        ).exists():
                            target_user.groups.add(grupo_moradores)
                    else:
                        # Remover do grupo Moradores se estiver
                        if target_user.groups.filter(
                            id=grupo_moradores.id
                        ).exists():
                            target_user.groups.remove(grupo_moradores)
                except Group.DoesNotExist:
                    return Response(
                        {"error": "Grupo Moradores não encontrado"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Validar/normalizar CPF e evitar colisão com o próprio registro
            if "cpf" in request.data and request.data["cpf"]:
                try:
                    cpf_normalizado = format_cpf(str(request.data["cpf"]))
                except Exception:
                    cpf_normalizado = str(request.data["cpf"])  # fallback

                if (
                    User.objects.filter(cpf=cpf_normalizado)
                    .exclude(id=target_user.id)
                    .exists()
                ):
                    return Response(
                        {"error": "CPF já cadastrado para outro usuário."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # aplica o cpf normalizado antes de salvar
                target_user.cpf = cpf_normalizado

            target_user.save()
            return Response({"message": "Atualizado com sucesso"})

        except User.DoesNotExist:
            return Response(
                {"error": "Usuário não encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
