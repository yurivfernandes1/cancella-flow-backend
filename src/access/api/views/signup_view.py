import re
from io import BytesIO

from app.utils.validators import validate_cpf
from cadastros.models import Condominio, Unidade
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()
USERNAME_REGEX = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])?$")


def _normalize_username(value):
    return str(value or "").strip().lower()


def _normalize_cpf_digits(value):
    return "".join(c for c in str(value or "") if c.isdigit())


def _normalize_phone_digits(value):
    return "".join(c for c in str(value or "") if c.isdigit())


def _validate_username(value):
    if not value:
        return False, "Nome de usuário é obrigatório."
    if not USERNAME_REGEX.match(value):
        return (
            False,
            "Nome de usuário inválido. Use 3 a 30 caracteres com letras minúsculas, números, ponto, hífen ou underline.",
        )
    if User.objects.filter(username=value).exists():
        return False, "Este nome de usuário já está em uso."
    return True, None


def _validate_cpf(value):
    cpf_digits = _normalize_cpf_digits(value)
    if len(cpf_digits) != 11:
        return False, "CPF deve conter 11 dígitos.", cpf_digits
    try:
        validate_cpf(cpf_digits)
    except ValidationError:
        return False, "CPF inválido.", cpf_digits
    if User.objects.filter(cpf=cpf_digits).exists():
        return False, "Este CPF já está em uso.", cpf_digits
    return True, None, cpf_digits


class SignupCondominioInfoView(APIView):
    """Retorna dados públicos mínimos do condomínio para a tela de cadastro por convite."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        try:
            condominio = Condominio.objects.get(
                signup_slug=slug, is_ativo=True
            )
        except Condominio.DoesNotExist:
            return Response(
                {"error": "Link de cadastro inválido ou inativo."},
                status=status.HTTP_404_NOT_FOUND,
            )

        unidades = (
            Unidade.objects.filter(
                is_active=True,
                created_by__condominio_id=condominio.id,
            )
            .distinct()
            .order_by("bloco", "numero")
        )

        return Response(
            {
                "condominio": {
                    "id": condominio.id,
                    "nome": condominio.nome,
                    "slug": condominio.signup_slug,
                    "logo_url": request.build_absolute_uri(
                        f"/api/access/signup/condominio/{condominio.signup_slug}/logo/"
                    ),
                },
                "unidades": [
                    {
                        "id": u.id,
                        "identificacao_completa": u.identificacao_completa,
                    }
                    for u in unidades
                ],
            }
        )


class SignupCondominioLogoView(APIView):
    """Serve logo do condomínio (público) para a tela de cadastro por convite."""

    permission_classes = [permissions.AllowAny]

    def get(self, _request, slug):
        try:
            condominio = Condominio.objects.get(
                signup_slug=slug, is_ativo=True
            )
        except Condominio.DoesNotExist:
            return Response(
                {"error": "Condomínio não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if getattr(condominio, "logo_db_data", None):
            return HttpResponse(
                bytes(condominio.logo_db_data),
                content_type=condominio.logo_db_content_type
                or "application/octet-stream",
            )

        if getattr(condominio, "logo", None):
            try:
                file_obj = condominio.logo
                file_obj.open("rb")
                content = file_obj.read()
                file_obj.close()
                return HttpResponse(content, content_type="image/*")
            except Exception:
                return Response(
                    {"error": "Logo não disponível."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        return Response(
            {"error": "Logo não cadastrada."},
            status=status.HTTP_404_NOT_FOUND,
        )


class SignupInviteLinkView(APIView):
    """Endpoint para síndico/admin obter (ou regenerar) link de cadastro de moradores."""

    permission_classes = [IsAuthenticated]

    def get_target_condominio(self, request):
        condominio_id = request.query_params.get("condominio_id")

        if (
            request.user.is_staff
            or request.user.groups.filter(name="admin").exists()
        ):
            if condominio_id:
                try:
                    return Condominio.objects.get(id=condominio_id)
                except Condominio.DoesNotExist:
                    return None
            if request.user.condominio_id:
                return Condominio.objects.filter(
                    id=request.user.condominio_id
                ).first()
            return None

        is_sindico = request.user.groups.filter(name="Síndicos").exists()
        if not is_sindico:
            return None

        if request.user.condominio_id:
            return Condominio.objects.filter(
                id=request.user.condominio_id
            ).first()
        return None

    def _build_response(self, request, condominio):
        frontend_base = request.query_params.get("frontend_base") or ""
        path = f"/signup/{condominio.signup_slug}"
        signup_url = (
            f"{frontend_base.rstrip('/')}{path}" if frontend_base else path
        )
        return {
            "condominio_id": condominio.id,
            "condominio_nome": condominio.nome,
            "signup_slug": condominio.signup_slug,
            "path": path,
            "signup_url": signup_url,
        }

    def get(self, request):
        condominio = self.get_target_condominio(request)
        if not condominio:
            return Response(
                {"error": "Você não tem permissão para acessar este convite."},
                status=status.HTTP_403_FORBIDDEN,
            )

        condominio.ensure_signup_credentials(force_regenerate=False)
        condominio.save(update_fields=["signup_slug"])
        return Response(self._build_response(request, condominio))

    def post(self, request):
        condominio = self.get_target_condominio(request)
        if not condominio:
            return Response(
                {
                    "error": "Você não tem permissão para regenerar este convite."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        condominio.ensure_signup_credentials(force_regenerate=True)
        condominio.save(update_fields=["signup_slug"])
        return Response(self._build_response(request, condominio))


class SignupInviteQrCodeView(SignupInviteLinkView):
    """Retorna PNG do QR Code do link de cadastro de moradores do condomínio."""

    def get(self, request):
        import qrcode

        condominio = self.get_target_condominio(request)
        if not condominio:
            return Response(
                {"error": "Você não tem permissão para acessar este convite."},
                status=status.HTTP_403_FORBIDDEN,
            )

        condominio.ensure_signup_credentials(force_regenerate=False)
        condominio.save(update_fields=["signup_slug"])

        payload = self._build_response(request, condominio)
        signup_url = payload.get("signup_url") or payload.get("path")

        qr_img = qrcode.make(str(signup_url))
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        buffer.seek(0)

        safe_nome = "".join(
            c if c.isalnum() or c in "-_" else "-"
            for c in str(condominio.nome or "condominio")
            .lower()
            .replace(" ", "-")
        )

        response = HttpResponse(buffer.read(), content_type="image/png")
        response["Content-Disposition"] = (
            f'attachment; filename="qrcode-cadastro-{safe_nome}.png"'
        )
        return response


class SignupView(APIView):
    """
    Cadastro público de moradores via link de convite do condomínio.
    Usuário é criado inativo (pendente de aprovação), com senha aleatória
    e first_access=True para troca obrigatória no primeiro login.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            username = _normalize_username(request.data.get("username"))
            is_username_ok, username_error = _validate_username(username)
            if not is_username_ok:
                return Response(
                    {"error": username_error},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            first_name = str(request.data.get("first_name") or "").strip()
            last_name = str(request.data.get("last_name") or "").strip()
            full_name = str(request.data.get("full_name") or "").strip()
            if not full_name:
                full_name = f"{first_name} {last_name}".strip()
            if not full_name:
                return Response(
                    {"error": "Nome completo é obrigatório."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            cpf_valid, cpf_error, cpf_digits = _validate_cpf(
                request.data.get("cpf")
            )
            if not cpf_valid:
                return Response(
                    {"error": cpf_error},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            email = str(request.data.get("email") or "").strip().lower()
            if not email:
                return Response(
                    {"error": "E-mail é obrigatório."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if User.objects.filter(email=email).exists():
                return Response(
                    {"error": "Este e-mail já está em uso."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            phone_digits = _normalize_phone_digits(request.data.get("phone"))
            if not phone_digits:
                return Response(
                    {"error": "Telefone é obrigatório."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            invite_slug = str(request.data.get("invite_slug") or "").strip()
            if not invite_slug:
                return Response(
                    {"error": "Convite inválido. Informe o condomínio."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                condominio = Condominio.objects.get(
                    signup_slug=invite_slug, is_ativo=True
                )
            except Condominio.DoesNotExist:
                return Response(
                    {"error": "Condomínio inválido ou inativo para cadastro."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            unidade_ids = request.data.get("unidade_ids")
            if isinstance(unidade_ids, str):
                unidade_ids = [
                    u.strip() for u in unidade_ids.split(",") if u.strip()
                ]
            unidade_ids = unidade_ids or []

            if not isinstance(unidade_ids, list) or not unidade_ids:
                return Response(
                    {"error": "Selecione ao menos uma unidade."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            unidades = Unidade.objects.filter(
                id__in=unidade_ids,
                is_active=True,
                created_by__condominio_id=condominio.id,
            ).distinct()

            if unidades.count() != len(set(str(u) for u in unidade_ids)):
                return Response(
                    {
                        "error": "Uma ou mais unidades são inválidas para este condomínio."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                senha_temporaria = User.objects.make_random_password()
                user = User.objects.create_user(
                    username=username,
                    password=senha_temporaria,
                    first_name=first_name,
                    last_name=last_name,
                    full_name=full_name,
                    cpf=cpf_digits,
                    phone=phone_digits,
                    email=email,
                    condominio=condominio,
                    is_active=False,
                    first_access=True,
                )
                user.unidades.add(*list(unidades))

                foto = request.FILES.get("foto")
                if foto:
                    user.foto_db_data = foto.read()
                    user.foto_db_content_type = foto.content_type
                    user.foto_db_filename = foto.name
                    user.save(
                        update_fields=[
                            "foto_db_data",
                            "foto_db_content_type",
                            "foto_db_filename",
                        ]
                    )

                moradores_group, _ = Group.objects.get_or_create(
                    name="Moradores"
                )
                user.groups.add(moradores_group)

                return Response(
                    {
                        "message": "Cadastro realizado com sucesso. O síndico precisa aprovar seu acesso.",
                        "username": user.username,
                        "temporary_password": senha_temporaria,
                        "status": "pendente_aprovacao",
                    },
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            return Response(
                {"error": f"Erro ao cadastrar usuário: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
