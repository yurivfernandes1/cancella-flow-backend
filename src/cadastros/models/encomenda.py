from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Encomenda(models.Model):
    unidade = models.ForeignKey(
        "cadastros.Unidade",
        on_delete=models.CASCADE,
        related_name="encomendas",
        null=True,
        blank=True,
        verbose_name="Unidade",
        help_text="Unidade destinatária da encomenda",
    )
    destinatario_nome = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Nome do Destinatário",
        help_text="Nome da pessoa que receberá a encomenda",
    )
    descricao = models.TextField(
        verbose_name="Descrição", help_text="Descrição da encomenda"
    )
    codigo_rastreio = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Código de Rastreio",
        help_text="Código de rastreamento da encomenda",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="encomendas_criadas",
        verbose_name="Criado por",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="encomendas_atualizadas",
        verbose_name="Atualizado por",
    )
    created_on = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    updated_on = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )
    retirado_por = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Retirado por",
        help_text="Nome da pessoa que retirou a encomenda",
    )
    retirado_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Retirado em",
        help_text="Data e hora em que a encomenda foi retirada",
    )

    class Meta:
        verbose_name = "Encomenda"
        verbose_name_plural = "Encomendas"
        ordering = ["-created_on"]

    def __str__(self):
        return f"Encomenda para {self.destinatario_nome} - Unidade {self.unidade} - {self.descricao[:50]}"

    @property
    def foi_retirada(self):
        """Retorna True se a encomenda já foi retirada"""
        return self.retirado_em is not None
