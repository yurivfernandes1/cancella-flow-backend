import uuid

from django.db import models

RESPOSTA_PRESENCA_PENDENTE = "pendente"
RESPOSTA_PRESENCA_CONFIRMADO = "confirmado"
RESPOSTA_PRESENCA_RECUSADO = "recusado"

RESPOSTA_PRESENCA_CHOICES = [
    (RESPOSTA_PRESENCA_PENDENTE, "Pendente"),
    (RESPOSTA_PRESENCA_CONFIRMADO, "Confirmado"),
    (RESPOSTA_PRESENCA_RECUSADO, "Recusado"),
]


class ListaConvidadosCerimonial(models.Model):
    evento = models.OneToOneField(
        "cadastros.EventoCerimonial",
        on_delete=models.CASCADE,
        related_name="lista_convidados",
        verbose_name="Evento",
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
        verbose_name = "Lista de Convidados (Cerimonial)"
        verbose_name_plural = "Listas de Convidados (Cerimonial)"

    def __str__(self):
        return f"{self.titulo} - {self.evento.nome}"


class ConvidadoListaCerimonial(models.Model):
    lista = models.ForeignKey(
        ListaConvidadosCerimonial,
        on_delete=models.CASCADE,
        related_name="convidados",
        verbose_name="Lista",
    )
    cpf = models.CharField(max_length=11, verbose_name="CPF")
    nome = models.CharField(max_length=255, verbose_name="Nome")
    email = models.EmailField(blank=True, default="", verbose_name="E-mail")
    vip = models.BooleanField(default=False, verbose_name="VIP")
    qr_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Token QR Code",
    )
    resposta_presenca = models.CharField(
        max_length=10,
        choices=RESPOSTA_PRESENCA_CHOICES,
        default=RESPOSTA_PRESENCA_PENDENTE,
        verbose_name="Resposta de Presença",
    )
    resposta_presenca_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Respondido em",
    )
    entrada_confirmada = models.BooleanField(default=False)
    entrada_em = models.DateTimeField(null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Convidado da Lista (Cerimonial)"
        verbose_name_plural = "Convidados da Lista (Cerimonial)"
        unique_together = [["lista", "cpf"]]
        ordering = ["-vip", "nome", "id"]

    def __str__(self):
        return f"{self.nome} ({self.cpf})"
