import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

LOCAL_TIPO_CHOICES = [
    ("espaco", "Espaço do Condomínio"),
    ("unidade", "Unidade do Morador"),
]


class ListaConvidados(models.Model):
    morador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listas_convidados",
        verbose_name="Morador",
    )
    titulo = models.CharField(max_length=255, verbose_name="Título")
    descricao = models.TextField(
        blank=True, default="", verbose_name="Descrição"
    )
    data_evento = models.DateField(
        null=True, blank=True, verbose_name="Data do Evento"
    )
    ativa = models.BooleanField(default=True, verbose_name="Ativa")
    local_tipo = models.CharField(
        max_length=10,
        choices=LOCAL_TIPO_CHOICES,
        blank=True,
        default="",
        verbose_name="Tipo de Local do Evento",
    )
    espaco = models.ForeignKey(
        "Espaco",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="listas_convidados",
        verbose_name="Espaço do Evento",
    )
    unidade_evento = models.ForeignKey(
        "Unidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="listas_convidados_evento",
        verbose_name="Unidade do Evento",
    )
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lista de Convidados"
        verbose_name_plural = "Listas de Convidados"

    def clean(self):
        if self.local_tipo == "espaco" and not self.espaco_id:
            raise ValidationError(
                {"espaco": "Selecione o espaço do condomínio."}
            )
        if self.local_tipo == "unidade" and not self.unidade_evento_id:
            raise ValidationError({"unidade_evento": "Selecione a unidade."})

    def __str__(self):
        return f"{self.titulo} – {self.morador}"


class ConvidadoLista(models.Model):
    lista = models.ForeignKey(
        ListaConvidados,
        on_delete=models.CASCADE,
        related_name="convidados",
        verbose_name="Lista",
    )
    cpf = models.CharField(max_length=11, verbose_name="CPF")
    nome = models.CharField(max_length=255, verbose_name="Nome")
    email = models.EmailField(
        blank=True, default="", verbose_name="E-mail do Convidado"
    )
    qr_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Token QR Code",
    )
    entrada_confirmada = models.BooleanField(
        default=False, verbose_name="Entrada Confirmada"
    )
    entrada_em = models.DateTimeField(
        null=True, blank=True, verbose_name="Data/Hora da Entrada"
    )
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Convidado"
        verbose_name_plural = "Convidados"
        unique_together = [["lista", "cpf"]]

    def __str__(self):
        return f"{self.nome} ({self.cpf})"
