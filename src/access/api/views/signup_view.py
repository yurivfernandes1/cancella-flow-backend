from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..serializers.signup_serializer import SignupSerializer

User = get_user_model()


class SignupView(APIView):
    """
    API para cadastro de novos usuários pelo público
    Os usuários são criados inativos por padrão e sem perfil.
    Qualquer usuário pode acessar esta API, sem necessidade de autenticação.
    """

    permission_classes = [
        permissions.AllowAny
    ]  # Permite acesso sem autenticação

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    username = serializer.validated_data["username"].strip()
                    full_name = serializer.validated_data["full_name"].strip()
                    cpf = serializer.validated_data["cpf"]
                    phone = serializer.validated_data["phone"]
                    email = serializer.validated_data["email"].strip()

                    # Verifica se o username já existe e adiciona um sufixo se necessário
                    base_username = username.lower()
                    username = base_username
                    counter = 1
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}_{counter}"
                        counter += 1

                    # Cria o usuário inativo
                    user = User.objects.create_user(
                        username=username,
                        password=User.objects.make_random_password(),  # Senha aleatória temporária
                        full_name=full_name,
                        cpf=cpf,
                        phone=phone,
                        email=email,
                        is_active=False,  # Inativo por padrão
                    )

                    return Response(
                        {
                            "message": "Cadastro realizado com sucesso. Um administrador irá revisar e ativar sua conta.",
                            "username": user.username,
                        },
                        status=status.HTTP_201_CREATED,
                    )
            except Exception as e:
                return Response(
                    {"error": f"Erro ao cadastrar usuário: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
