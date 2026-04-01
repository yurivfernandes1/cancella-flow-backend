import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventoCerimonial",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "nome",
                    models.CharField(max_length=255, verbose_name="Nome"),
                ),
                (
                    "datetime_inicio",
                    models.DateTimeField(verbose_name="Início"),
                ),
                ("datetime_fim", models.DateTimeField(verbose_name="Término")),
                (
                    "cep",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="CEP do local do evento (somente números)",
                        max_length=8,
                        verbose_name="CEP",
                    ),
                ),
                (
                    "numero",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Número do endereço do evento",
                        max_length=10,
                        verbose_name="Número",
                    ),
                ),
                (
                    "complemento",
                    models.CharField(
                        blank=True,
                        help_text="Complemento do endereço (opcional)",
                        max_length=100,
                        null=True,
                        verbose_name="Complemento",
                    ),
                ),
                (
                    "numero_pessoas",
                    models.PositiveIntegerField(
                        default=1,
                        verbose_name="Número de Pessoas",
                    ),
                ),
                (
                    "evento_confirmado",
                    models.BooleanField(
                        default=False,
                        verbose_name="Evento Confirmado",
                    ),
                ),
                (
                    "imagem_db_data",
                    models.BinaryField(
                        blank=True,
                        help_text="Dados binários da imagem armazenados no banco",
                        null=True,
                    ),
                ),
                (
                    "imagem_db_content_type",
                    models.CharField(
                        blank=True,
                        help_text="Content-Type da imagem",
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "imagem_db_filename",
                    models.CharField(
                        blank=True,
                        help_text="Nome original do arquivo de imagem",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cerimonialistas",
                    models.ManyToManyField(
                        related_name="eventos_cerimonial_como_cerimonialista",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Cerimonialistas",
                    ),
                ),
                (
                    "organizadores",
                    models.ManyToManyField(
                        blank=True,
                        related_name="eventos_cerimonial_como_organizador",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Organizadores",
                    ),
                ),
                (
                    "funcionarios",
                    models.ManyToManyField(
                        blank=True,
                        related_name="eventos_cerimonial_como_funcionario",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Funcionários",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="eventos_cerimonial_criados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="eventos_cerimonial_atualizados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Evento Cerimonial",
                "verbose_name_plural": "Eventos Cerimonial",
                "ordering": ["datetime_inicio"],
            },
        ),
        migrations.CreateModel(
            name="ListaConvidadosCerimonial",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "titulo",
                    models.CharField(max_length=255, verbose_name="Título"),
                ),
                (
                    "descricao",
                    models.TextField(
                        blank=True, default="", verbose_name="Descrição"
                    ),
                ),
                (
                    "data_evento",
                    models.DateField(
                        blank=True, null=True, verbose_name="Data do Evento"
                    ),
                ),
                (
                    "ativa",
                    models.BooleanField(default=True, verbose_name="Ativa"),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
                (
                    "evento",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lista_convidados",
                        to="cadastros.eventocerimonial",
                        verbose_name="Evento",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lista de Convidados (Cerimonial)",
                "verbose_name_plural": "Listas de Convidados (Cerimonial)",
            },
        ),
        migrations.CreateModel(
            name="ConvidadoListaCerimonial",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("cpf", models.CharField(max_length=11, verbose_name="CPF")),
                (
                    "nome",
                    models.CharField(max_length=255, verbose_name="Nome"),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True,
                        default="",
                        max_length=254,
                        verbose_name="E-mail",
                    ),
                ),
                (
                    "vip",
                    models.BooleanField(default=False, verbose_name="VIP"),
                ),
                (
                    "qr_token",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        verbose_name="Token QR Code",
                    ),
                ),
                ("entrada_confirmada", models.BooleanField(default=False)),
                ("entrada_em", models.DateTimeField(blank=True, null=True)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                (
                    "lista",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="convidados",
                        to="cadastros.listaconvidadoscerimonial",
                        verbose_name="Lista",
                    ),
                ),
            ],
            options={
                "verbose_name": "Convidado da Lista (Cerimonial)",
                "verbose_name_plural": "Convidados da Lista (Cerimonial)",
                "ordering": ["-vip", "nome", "id"],
                "unique_together": {("lista", "cpf")},
            },
        ),
        migrations.CreateModel(
            name="EventoCerimonialConvite",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("organizador", "Organizador do Evento"),
                            ("recepcao", "Recepção"),
                        ],
                        max_length=20,
                    ),
                ),
                ("token", models.UUIDField(default=uuid.uuid4, unique=True)),
                ("ativo", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="convites_evento_cerimonial_criados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "evento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="convites",
                        to="cadastros.eventocerimonial",
                        verbose_name="Evento",
                    ),
                ),
            ],
            options={
                "verbose_name": "Convite de Evento Cerimonial",
                "verbose_name_plural": "Convites de Evento Cerimonial",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="EventoCerimonialFuncionario",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "nome",
                    models.CharField(max_length=255, verbose_name="Nome"),
                ),
                (
                    "documento",
                    models.CharField(max_length=14, verbose_name="Documento"),
                ),
                (
                    "funcao",
                    models.CharField(max_length=100, verbose_name="Função"),
                ),
                (
                    "horario_entrada",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Horário de Entrada",
                    ),
                ),
                (
                    "horario_saida",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Horário de Saída",
                    ),
                ),
                (
                    "pagamento_realizado",
                    models.BooleanField(
                        default=False,
                        verbose_name="Pagamento Realizado",
                    ),
                ),
                (
                    "valor_pagamento",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        verbose_name="Valor a Pagar",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "evento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="funcionarios_evento",
                        to="cadastros.eventocerimonial",
                        verbose_name="Evento",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="eventos_cerimonial_funcionario_vinculos",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Usuário",
                    ),
                ),
            ],
            options={
                "verbose_name": "Funcionário do Evento Cerimonial",
                "verbose_name_plural": "Funcionários do Evento Cerimonial",
                "ordering": ["nome", "id"],
                "unique_together": {("evento", "documento")},
            },
        ),
        migrations.AddConstraint(
            model_name="eventocerimonialconvite",
            constraint=models.UniqueConstraint(
                fields=("evento", "tipo"),
                name="unique_convite_ativo_por_evento_tipo",
                condition=models.Q(ativo=True),
            ),
        ),
    ]
