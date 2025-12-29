from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

User = get_user_model()


class Espaco(models.Model):
    nome = models.CharField(max_length=255)
    capacidade_pessoas = models.PositiveIntegerField(default=0)
    valor_aluguel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Valor do Aluguel",
        help_text="Valor cobrado pela reserva do espaço por dia",
    )
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="espacos_criados",
        verbose_name="Criado por",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="espacos_atualizados",
        verbose_name="Atualizado por",
    )
    created_on = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    updated_on = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Espaço"
        verbose_name_plural = "Espaços"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class EspacoInventarioItem(models.Model):
    espaco = models.ForeignKey(
        Espaco,
        on_delete=models.CASCADE,
        related_name="inventario_itens",
        verbose_name="Espaço",
    )
    nome = models.CharField(max_length=255)
    codigo = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="espaco_itens_criados",
        verbose_name="Criado por",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="espaco_itens_atualizados",
        verbose_name="Atualizado por",
    )
    created_on = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    updated_on = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Item de Inventário do Espaço"
        verbose_name_plural = "Itens de Inventário dos Espaços"
        ordering = ["espaco__nome", "nome"]
        unique_together = [["espaco", "codigo"]]

    def __str__(self):
        return f"{self.nome} ({self.codigo}) - {self.espaco.nome}"


class EspacoReserva(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("confirmada", "Confirmada"),
        ("cancelada", "Cancelada"),
    ]

    espaco = models.ForeignKey(
        Espaco,
        on_delete=models.CASCADE,
        related_name="reservas",
        verbose_name="Espaço",
    )
    morador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reservas_espacos",
        # limitar a Moradores (e opcionalmente Síndicos)
        limit_choices_to=models.Q(groups__name__iexact="Moradores")
        | models.Q(groups__name__iexact="Síndicos")
        | models.Q(groups__name__iexact="Sindicos"),
        verbose_name="Morador",
    )
    data_reserva = models.DateField(
        verbose_name="Data da Reserva",
        help_text="Data do dia reservado (dia completo)",
    )
    valor_cobrado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Valor Cobrado",
        help_text="Valor que será cobrado pela reserva",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="confirmada",
        verbose_name="Status",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas_criadas",
        verbose_name="Criado por",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas_atualizadas",
        verbose_name="Atualizado por",
    )
    created_on = models.DateTimeField(
        auto_now_add=True, verbose_name="Criado em"
    )
    updated_on = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Reserva de Espaço"
        verbose_name_plural = "Reservas de Espaço"
        ordering = ["-data_reserva"]
        unique_together = [
            ["espaco", "data_reserva"]
        ]  # Apenas uma reserva por dia por espaço

    def __str__(self):
        return f"{self.espaco.nome} - {self.morador.get_full_name()} em {self.data_reserva}"

    def clean(self):
        # Apenas validar datas para novas reservas ou quando a data for alterada
        if self.pk:
            # Buscar a instância original do banco
            try:
                original = EspacoReserva.objects.get(pk=self.pk)
                # Se a data não mudou, não validar (permite alterar apenas status)
                if original.data_reserva == self.data_reserva:
                    return
            except EspacoReserva.DoesNotExist:
                pass

        # Validar que a data não é retroativa
        hoje = timezone.now().date()
        if self.data_reserva < hoje:
            raise ValidationError(
                {"data_reserva": "Não é permitido reservar datas retroativas."}
            )

        # Validar que a data está dentro do limite de 1 ano
        limite_futuro = hoje + timedelta(days=365)
        # Ajustar para o último dia do mês do limite
        ultimo_dia_mes = limite_futuro.replace(day=1)
        if limite_futuro.month == 12:
            ultimo_dia_mes = ultimo_dia_mes.replace(
                year=limite_futuro.year + 1, month=1
            )
        else:
            ultimo_dia_mes = ultimo_dia_mes.replace(
                month=limite_futuro.month + 1
            )
        ultimo_dia_mes = ultimo_dia_mes - timedelta(days=1)

        if self.data_reserva > ultimo_dia_mes:
            raise ValidationError(
                {
                    "data_reserva": f"Não é permitido reservar após {ultimo_dia_mes.strftime('%d/%m/%Y')}."
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
