from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models


class Aviso(models.Model):
    PRIORIDADE_BAIXA = "baixa"
    PRIORIDADE_MEDIA = "media"
    PRIORIDADE_ALTA = "alta"
    PRIORIDADE_URGENTE = "urgente"

    PRIORIDADE_CHOICES = [
        (PRIORIDADE_BAIXA, "Baixa"),
        (PRIORIDADE_MEDIA, "Média"),
        (PRIORIDADE_ALTA, "Alta"),
        (PRIORIDADE_URGENTE, "Urgente"),
    ]

    STATUS_RASCUNHO = "rascunho"
    STATUS_ATIVO = "ativo"
    STATUS_INATIVO = "inativo"

    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_ATIVO, "Ativo"),
        (STATUS_INATIVO, "Inativo"),
    ]

    titulo = models.CharField(max_length=255)
    descricao = models.TextField()
    grupo = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="avisos",
        help_text="Grupo de usuários que verá este aviso",
    )
    prioridade = models.CharField(
        max_length=10, choices=PRIORIDADE_CHOICES, default=PRIORIDADE_MEDIA
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_ATIVO
    )
    data_inicio = models.DateTimeField()
    data_fim = models.DateTimeField(null=True, blank=True)

    # Controle/auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="avisos_criados",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="avisos_atualizados",
    )

    class Meta:
        verbose_name = "Aviso"
        verbose_name_plural = "Avisos"
        ordering = ["-prioridade", "-data_inicio", "-created_at"]

    def __str__(self):
        return f"[{self.get_prioridade_display()}] {self.titulo}"

    @property
    def is_vigente(self):
        from django.utils import timezone

        now = timezone.now()
        if self.status != self.STATUS_ATIVO:
            return False
        if self.data_inicio and self.data_inicio > now:
            return False
        if self.data_fim and self.data_fim < now:
            return False
        return True
