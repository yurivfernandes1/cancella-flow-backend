import uuid

from django.conf import settings
from django.db import models


class EventoCerimonial(models.Model):
    nome = models.CharField(max_length=255, verbose_name="Nome")
    datetime_inicio = models.DateTimeField(verbose_name="Início")
    datetime_fim = models.DateTimeField(verbose_name="Término")

    cep = models.CharField(
        max_length=8,
        blank=True,
        default="",
        verbose_name="CEP",
        help_text="CEP do local do evento (somente números)",
    )
    numero = models.CharField(
        max_length=10,
        blank=True,
        default="",
        verbose_name="Número",
        help_text="Número do endereço do evento",
    )
    complemento = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Complemento",
        help_text="Complemento do endereço (opcional)",
    )

    numero_pessoas = models.PositiveIntegerField(
        default=1,
        verbose_name="Número de Pessoas",
    )
    evento_confirmado = models.BooleanField(
        default=False,
        verbose_name="Evento Confirmado",
    )

    imagem_db_data = models.BinaryField(
        null=True,
        blank=True,
        help_text="Dados binários da imagem armazenados no banco",
    )
    imagem_db_content_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Content-Type da imagem",
    )
    imagem_db_filename = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Nome original do arquivo de imagem",
    )

    cerimonialistas = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="eventos_cerimonial_como_cerimonialista",
        verbose_name="Cerimonialistas",
    )
    organizadores = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="eventos_cerimonial_como_organizador",
        blank=True,
        verbose_name="Organizadores",
    )
    funcionarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="eventos_cerimonial_como_funcionario",
        blank=True,
        verbose_name="Funcionários",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_cerimonial_criados",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_cerimonial_atualizados",
    )

    class Meta:
        verbose_name = "Evento Cerimonial"
        verbose_name_plural = "Eventos Cerimonial"
        ordering = ["datetime_inicio"]

    def __str__(self):
        return self.nome


class EventoCerimonialConvite(models.Model):
    TIPO_ORGANIZADOR = "organizador"
    TIPO_RECEPCAO = "recepcao"
    TIPO_CHOICES = [
        (TIPO_ORGANIZADOR, "Organizador do Evento"),
        (TIPO_RECEPCAO, "Recepção"),
    ]

    evento = models.ForeignKey(
        EventoCerimonial,
        on_delete=models.CASCADE,
        related_name="convites",
        verbose_name="Evento",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="convites_evento_cerimonial_criados",
    )

    class Meta:
        verbose_name = "Convite de Evento Cerimonial"
        verbose_name_plural = "Convites de Evento Cerimonial"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "tipo", "ativo"],
                name="unique_convite_ativo_por_evento_tipo",
                condition=models.Q(ativo=True),
            )
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.evento.nome}"


class EventoCerimonialFuncionario(models.Model):
    evento = models.ForeignKey(
        EventoCerimonial,
        on_delete=models.CASCADE,
        related_name="funcionarios_evento",
        verbose_name="Evento",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_cerimonial_funcionario_vinculos",
        verbose_name="Usuário",
    )
    nome = models.CharField(max_length=255, verbose_name="Nome")
    documento = models.CharField(max_length=14, verbose_name="Documento")
    funcao = models.CharField(max_length=100, verbose_name="Função")
    horario_entrada = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Horário de Entrada",
    )
    horario_saida = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Horário de Saída",
    )
    pagamento_realizado = models.BooleanField(
        default=False,
        verbose_name="Pagamento Realizado",
    )
    valor_pagamento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Valor a Pagar",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Funcionário do Evento Cerimonial"
        verbose_name_plural = "Funcionários do Evento Cerimonial"
        ordering = ["nome", "id"]
        unique_together = [["evento", "documento"]]

    def __str__(self):
        return f"{self.nome} - {self.evento.nome}"

    @property
    def documento_mascarado(self):
        digits = "".join(
            ch for ch in str(self.documento or "") if ch.isdigit()
        )
        if len(digits) >= 6:
            return f"{digits[:3]}*****{digits[-3:]}"
        return self.documento
