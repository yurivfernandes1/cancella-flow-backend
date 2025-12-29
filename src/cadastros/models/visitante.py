import re

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

User = get_user_model()


def validate_placa_brasileira(value):
    """
    Valida placa de veículo brasileira nos formatos:
    - Antigo (Mercosul): ABC-1234 ou ABC1234
    - Novo (Mercosul): ABC1D23 ou ABC-1D23
    """
    if not value:
        return

    # Remove espaços e converte para maiúsculas
    placa = value.strip().upper().replace("-", "").replace(" ", "")

    # Formato antigo: 3 letras + 4 números (ABC1234)
    formato_antigo = re.match(r"^[A-Z]{3}\d{4}$", placa)

    # Formato novo Mercosul: 3 letras + 1 número + 1 letra + 2 números (ABC1D23)
    formato_mercosul = re.match(r"^[A-Z]{3}\d[A-Z]\d{2}$", placa)

    if not (formato_antigo or formato_mercosul):
        raise ValidationError(
            "Placa inválida. Use o formato ABC-1234 (antigo) ou ABC1D23 (Mercosul)."
        )


class Visitante(models.Model):
    morador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="visitantes",
        limit_choices_to={"groups__name": "Moradores"},
        verbose_name="Morador",
        help_text="Morador que está recebendo o visitante",
    )
    nome = models.CharField(
        max_length=255,
        verbose_name="Nome do Visitante",
        help_text="Nome completo do visitante",
    )
    documento = models.CharField(
        max_length=20,
        verbose_name="Documento",
        help_text="CPF, RG ou outro documento de identificação",
    )
    placa_veiculo = models.CharField(
        max_length=8,
        null=True,
        blank=True,
        verbose_name="Placa do Veículo",
        help_text="Placa do veículo do visitante (opcional, formato ABC-1234 ou ABC1D23)",
        validators=[validate_placa_brasileira],
    )
    data_entrada = models.DateTimeField(
        verbose_name="Data de Entrada",
        help_text="Data e hora de entrada do visitante",
    )
    data_saida = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Saída",
        help_text="Data e hora de saída do visitante",
    )
    is_permanente = models.BooleanField(
        default=False,
        verbose_name="Visitante Permanente",
        help_text="Marque se o visitante tem acesso permanente",
    )
    created_on = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    updated_on = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Visitante"
        verbose_name_plural = "Visitantes"
        ordering = ["-data_entrada"]

    def __str__(self):
        return f"{self.nome} - Visitando {self.morador.full_name}"

    @property
    def esta_no_condominio(self):
        """Retorna True se o visitante ainda está no condomínio"""
        return self.data_saida is None

    @property
    def tempo_permanencia(self):
        """Retorna o tempo de permanência do visitante"""
        from django.utils import timezone

        if self.data_saida:
            return self.data_saida - self.data_entrada
        else:
            return timezone.now() - self.data_entrada
            return timezone.now() - self.data_entrada
