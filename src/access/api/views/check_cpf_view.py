from app.utils.validators import validate_cpf
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()


class CheckCpfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, cpf):
        cpf_digits = "".join(c for c in str(cpf or "") if c.isdigit())

        if len(cpf_digits) != 11:
            return Response(
                {
                    "cpf": cpf_digits,
                    "valid": False,
                    "available": False,
                    "message": "CPF deve conter 11 dígitos.",
                }
            )

        try:
            validate_cpf(cpf_digits)
        except ValidationError:
            return Response(
                {
                    "cpf": cpf_digits,
                    "valid": False,
                    "available": False,
                    "message": "CPF inválido.",
                }
            )

        available = not User.objects.filter(cpf=cpf_digits).exists()
        return Response(
            {
                "cpf": cpf_digits,
                "valid": True,
                "available": available,
                "message": None if available else "CPF já cadastrado.",
            }
        )
