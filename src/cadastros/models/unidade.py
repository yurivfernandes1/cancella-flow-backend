from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Unidade(models.Model):
    numero = models.CharField(
        max_length=20,
        verbose_name="Número da Unidade",
        help_text="Número ou identificação da unidade (ex: 101, 201A, etc.)",
    )
    bloco = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="Bloco",
        help_text="Bloco ou torre onde a unidade está localizada",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Indica se a unidade está ativa no sistema",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unidades_criadas",
        verbose_name="Criado por",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unidades_atualizadas",
        verbose_name="Atualizado por",
    )
    created_on = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    updated_on = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Unidade"
        verbose_name_plural = "Unidades"
        ordering = ["bloco", "numero"]

    def __str__(self):
        if self.bloco:
            return f"Unidade {self.numero} - Bloco {self.bloco}"
        return f"Unidade {self.numero}"

    @property
    def identificacao_completa(self):
        """Retorna a identificação completa da unidade"""
        if self.bloco:
            return f"Bl. {self.bloco} - Unid. {self.numero}"
        return f"Unid. {self.numero}"
