import re

from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()
USERNAME_REGEX = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])?$")


class CheckUsernameView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, username):
        normalized = str(username or "").strip().lower()
        pattern_ok = bool(USERNAME_REGEX.match(normalized))
        available = (
            pattern_ok
            and not User.objects.filter(username=normalized).exists()
        )
        return Response(
            {
                "username": normalized,
                "available": available,
                "pattern_ok": pattern_ok,
                "message": None
                if available
                else (
                    "Nome de usuário fora do padrão."
                    if not pattern_ok
                    else "Nome de usuário já está em uso."
                ),
            }
        )
