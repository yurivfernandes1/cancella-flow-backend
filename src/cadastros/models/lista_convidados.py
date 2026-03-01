from django.conf import settings
from django.db import models


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
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lista de Convidados"
        verbose_name_plural = "Listas de Convidados"

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
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Convidado"
        verbose_name_plural = "Convidados"
        unique_together = [["lista", "cpf"]]

    def __str__(self):
        return f"{self.nome} ({self.cpf})"
