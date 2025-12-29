from app.utils.image_validators import validate_logo_file
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
    logo = models.FileField(
        upload_to="condominios/logos/",
        null=True,
        blank=True,
        validators=[validate_logo_file],
        help_text="Logo quadrada até 250x250px (png, jpg, jpeg, svg)",
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
