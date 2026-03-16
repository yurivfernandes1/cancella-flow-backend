import secrets
import string

from django.db import models


class Condominio(models.Model):
    nome = models.CharField(
        max_length=255,
        verbose_name="Nome do Condomínio",
        help_text="Nome completo do condomínio",
    )
    cnpj = models.CharField(
        max_length=18,
        unique=True,
        verbose_name="CNPJ",
        help_text="CNPJ no formato XX.XXX.XXX/XXXX-XX",
    )
    telefone = models.CharField(
        max_length=15,
        verbose_name="Telefone",
        help_text="Telefone de contato do condomínio",
    )
    cep = models.CharField(
        max_length=8,
        blank=True,
        default="",
        verbose_name="CEP",
        help_text="CEP do condomínio (somente números)",
    )
    numero = models.CharField(
        max_length=10,
        blank=True,
        default="",
        verbose_name="Número",
        help_text="Número do endereço",
    )
    complemento = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Complemento",
        help_text="Complemento do endereço (opcional)",
    )
    signup_slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Slug de cadastro",
        help_text="Slug único usado no link de cadastro de moradores",
    )
    signup_token = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        verbose_name="Token de cadastro",
        help_text="Token secreto para validar o link de cadastro de moradores",
    )
    logo = models.FileField(
        upload_to="condominios/logos/",
        null=True,
        blank=True,
        help_text="Logo do condomínio (png, jpg, jpeg, svg — qualquer tamanho)",
    )
    # Campos para armazenar logo diretamente no banco (BLOB)
    logo_db_data = models.BinaryField(
        null=True,
        blank=True,
        help_text="Dados binários da logo (se armazenada no DB)",
    )
    logo_db_content_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Content-Type do arquivo",
    )
    logo_db_filename = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Nome original do arquivo",
    )
    is_ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Indica se o condomínio está ativo",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Condomínio"
        verbose_name_plural = "Condomínios"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def ensure_signup_credentials(self, force_regenerate=False):
        if force_regenerate or not self.signup_slug:
            alphabet = string.ascii_lowercase + string.digits
            candidate = ""
            while (
                not candidate
                or Condominio.objects.filter(signup_slug=candidate)
                .exclude(id=self.id)
                .exists()
            ):
                random_part = "".join(
                    secrets.choice(alphabet) for _ in range(12)
                )
                candidate = f"cad-{random_part}"
            self.signup_slug = candidate

    def save(self, *args, **kwargs):
        self.ensure_signup_credentials()
        super().save(*args, **kwargs)


class CondominioLogo(models.Model):
    """
    Armazena a logo do condomínio como BLOB no banco de dados.
    Usado quando o time preferir armazenar imagens diretamente no DB.
    """

    condominio = models.OneToOneField(
        Condominio,
        on_delete=models.CASCADE,
        related_name="logo_db",
        verbose_name="Condomínio",
    )
    data = models.BinaryField(null=True, blank=True)
    content_type = models.CharField(max_length=100, blank=True, null=True)
    filename = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Logo do Condomínio (DB)"
        verbose_name_plural = "Logos de Condomínios (DB)"

    def __str__(self):
        return self.nome
