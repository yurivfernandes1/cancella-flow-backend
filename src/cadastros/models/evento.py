from django.conf import settings
from django.db import models


class Evento(models.Model):
    titulo = models.CharField(
        max_length=255, verbose_name="Título", help_text="Título do evento"
    )
    descricao = models.TextField(
        verbose_name="Descrição", help_text="Descrição detalhada do evento"
    )
    espaco = models.ForeignKey(
        "cadastros.Espaco",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos",
        verbose_name="Espaço",
        help_text="Espaço onde o evento acontecerá (opcional)",
    )
    local_texto = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Local (texto)",
        help_text="Descrição do local quando não for um espaço cadastrado",
    )
    datetime_inicio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Início",
        help_text="Data e hora de início do evento",
    )
    datetime_fim = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Término",
        help_text="Data e hora de término do evento",
    )
    imagem = models.ImageField(
        upload_to="eventos/",
        null=True,
        blank=True,
        verbose_name="Imagem",
        help_text="Imagem ilustrativa do evento (legado — prefer imagem_db)",
    )
    # Armazenamento da imagem como BLOB no banco (mesma abordagem do condomínio)
    imagem_db_data = models.BinaryField(
        null=True,
        blank=True,
        help_text="Dados binários da imagem armazenados no banco",
    )
    imagem_db_content_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Content-Type do arquivo de imagem",
    )
    imagem_db_filename = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Nome original do arquivo de imagem",
    )

    # Controle/auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_criados",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_atualizados",
    )

    class Meta:
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"

    ordering = ["datetime_inicio"]

    def __str__(self):
        if self.datetime_inicio:
            return f"{self.titulo} - {self.datetime_inicio.strftime('%d/%m/%Y %H:%M')}"
        return self.titulo

    @property
    def local_completo(self):
        """Retorna o local do evento (espaço ou texto)"""
        if self.espaco:
            return self.espaco.nome
        return self.local_texto or "Local não especificado"

    def clean(self):
        from django.core.exceptions import ValidationError

        # Validar que pelo menos um local foi informado
        if not self.espaco and not self.local_texto:
            raise ValidationError(
                "Informe um espaço cadastrado ou descreva o local do evento."
            )

        # Validar que término > início
        if self.datetime_inicio and self.datetime_fim:
            if self.datetime_fim <= self.datetime_inicio:
                raise ValidationError(
                    "A hora de término deve ser posterior à hora de início."
                )
