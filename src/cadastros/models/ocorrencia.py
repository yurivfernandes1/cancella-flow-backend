from django.conf import settings
from django.db import models


class Ocorrencia(models.Model):
    TIPO_PROBLEMA = "problema"
    TIPO_SUGESTAO = "sugestao"
    TIPO_CHOICES = [
        (TIPO_PROBLEMA, "Problema"),
        (TIPO_SUGESTAO, "Sugestão"),
    ]

    STATUS_ABERTA = "aberta"
    STATUS_EM_ANDAMENTO = "em_andamento"
    STATUS_RESOLVIDA = "resolvida"
    STATUS_FECHADA = "fechada"
    STATUS_CHOICES = [
        (STATUS_ABERTA, "Aberta"),
        (STATUS_EM_ANDAMENTO, "Em Andamento"),
        (STATUS_RESOLVIDA, "Resolvida"),
        (STATUS_FECHADA, "Fechada"),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=255)
    descricao = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ABERTA
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ocorrencias_criadas",
    )
    resposta = models.TextField(null=True, blank=True)
    respondido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_respondidas",
    )
    respondido_em = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ocorrência"
        verbose_name_plural = "Ocorrências"

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.titulo} ({self.get_status_display()})"
