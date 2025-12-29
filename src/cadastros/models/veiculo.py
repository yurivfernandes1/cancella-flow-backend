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


class Veiculo(models.Model):
    """Model para veículos dos moradores"""

    placa = models.CharField(
        max_length=8,
        verbose_name="Placa",
        help_text="Placa do veículo (formato ABC-1234 ou ABC1D23)",
        validators=[validate_placa_brasileira],
    )
    marca_modelo = models.CharField(
        max_length=100,
        verbose_name="Marca e Modelo",
        help_text="Marca e modelo do veículo (ex: Toyota Corolla)",
    )
    morador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="veiculos",
        limit_choices_to=models.Q(groups__name__iexact="Moradores")
        | models.Q(groups__name__iexact="Síndicos")
        | models.Q(groups__name__iexact="Sindicos"),
        verbose_name="Morador",
        help_text="Morador proprietário do veículo",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Indica se o veículo está ativo no sistema",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="veiculos_criados",
        verbose_name="Criado por",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="veiculos_atualizados",
        verbose_name="Atualizado por",
    )
    created_on = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    updated_on = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Veículo"
        verbose_name_plural = "Veículos"
        ordering = ["-created_on"]
        unique_together = [["placa", "morador"]]

    def __str__(self):
        return f"{self.placa} - {self.marca_modelo}"

    def clean(self):
        """Validação adicional antes de salvar"""
        super().clean()

        # Normalizar placa (remover hífen e converter para maiúsculas)
        if self.placa:
            self.placa = (
                self.placa.strip().upper().replace("-", "").replace(" ", "")
            )

        # Validar placa
        validate_placa_brasileira(self.placa)

    def save(self, *args, **kwargs):
        """Sobrescreve save para garantir validação"""
        self.clean()
        super().save(*args, **kwargs)
