from app.utils.validators import (
    format_cpf,
    format_phone,
    validate_cpf,
    validate_phone,
)
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    username = models.CharField(
        max_length=150,
        unique=True,
        error_messages={
            "unique": "Este nome de usuário já está em uso.",
        },
    )
    full_name = models.CharField(max_length=255)
    cpf = models.CharField(
        max_length=14,
        unique=True,
        validators=[validate_cpf],
        verbose_name="CPF",
        help_text="CPF no formato XXX.XXX.XXX-XX ou apenas números",
    )
    phone = models.CharField(
        max_length=15,
        validators=[validate_phone],
        verbose_name="Telefone",
        help_text="Telefone no formato (XX) XXXXX-XXXX ou apenas números",
    )
    first_access = models.BooleanField(
        default=True,
        verbose_name="Primeiro Acesso",
        help_text="Indica se o usuário ainda não alterou a senha padrão",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_users",
    )
    condominio = models.ForeignKey(
        "cadastros.Condominio",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="usuarios",
        verbose_name="Condomínio",
    )
    unidade = models.ForeignKey(
        "cadastros.Unidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="morador",
        verbose_name="Unidade",
        help_text="Unidade onde o morador reside",
    )

    def save(self, *args, **kwargs):
        if self.full_name:
            self.full_name = " ".join(
                word.capitalize() for word in self.full_name.split()
            )
        self.username = self.username.lower()

        # Formatar CPF se fornecido
        if self.cpf:
            self.cpf = format_cpf(self.cpf)

        # Formatar telefone se fornecido
        if self.phone:
            self.phone = format_phone(self.phone)

        # Usamos o is_active padrão do Django
        self.is_active = self.is_active
        super().save(*args, **kwargs)

    @property
    def is_ativo(self):
        return self.is_active

    @is_ativo.setter
    def is_ativo(self, value):
        self.is_active = value

    def __str__(self):
        return f"{self.full_name} ({self.username})"

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        ordering = ["full_name"]
