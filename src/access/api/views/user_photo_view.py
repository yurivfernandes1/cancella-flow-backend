from django.contrib.auth import get_user_model
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()


class UserPhotoView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_target_user(self, request, user_id=None):
        if user_id is None or str(request.user.id) == str(user_id):
            return request.user

        if request.user.is_staff:
            return User.objects.filter(id=user_id).first()

        is_sindico = request.user.groups.filter(name="Síndicos").exists()
        if is_sindico:
            candidate = User.objects.filter(id=user_id).first()
            if (
                candidate
                and candidate.condominio_id == request.user.condominio_id
            ):
                return candidate

        return None

    def get(self, request, user_id=None):
        target_user = self._get_target_user(request, user_id)
        if not target_user:
            return Response(
                {"error": "Você não tem permissão para acessar esta foto."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not target_user.foto_db_data:
            return Response(
                {"error": "Foto não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return HttpResponse(
            bytes(target_user.foto_db_data),
            content_type=target_user.foto_db_content_type
            or "application/octet-stream",
        )

    def post(self, request, user_id=None):
        target_user = self._get_target_user(request, user_id)
        if not target_user:
            return Response(
                {"error": "Você não tem permissão para atualizar esta foto."},
                status=status.HTTP_403_FORBIDDEN,
            )

        foto = request.FILES.get("foto")
        if not foto:
            return Response(
                {"error": "Nenhum arquivo 'foto' enviado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_user.foto_db_data = foto.read()
        target_user.foto_db_content_type = foto.content_type
        target_user.foto_db_filename = foto.name
        target_user.save(
            update_fields=[
                "foto_db_data",
                "foto_db_content_type",
                "foto_db_filename",
            ]
        )

        return Response({"message": "Foto de perfil salva com sucesso."})
