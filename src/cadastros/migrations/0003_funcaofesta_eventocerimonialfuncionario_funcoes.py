from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0002_convidadolistacerimonial_vip_ordering"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FuncaoFesta",
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
                    models.CharField(max_length=120, verbose_name="Nome"),
                ),
                (
                    "ativo",
                    models.BooleanField(default=True, verbose_name="Ativo"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="funcoes_festa_criadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="funcoes_festa_atualizadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Função de Festa",
                "verbose_name_plural": "Funções de Festa",
                "ordering": ["nome", "id"],
                "unique_together": {("created_by", "nome")},
            },
        ),
        migrations.AlterField(
            model_name="eventocerimonialfuncionario",
            name="funcao",
            field=models.CharField(
                blank=True,
                default="",
                max_length=100,
                verbose_name="Função",
            ),
        ),
        migrations.AddField(
            model_name="eventocerimonialfuncionario",
            name="is_recepcao",
            field=models.BooleanField(default=False, verbose_name="Recepção"),
        ),
        migrations.AddField(
            model_name="eventocerimonialfuncionario",
            name="funcoes",
            field=models.ManyToManyField(
                blank=True,
                related_name="funcionarios_evento",
                to="cadastros.funcaofesta",
                verbose_name="Funções",
            ),
        ),
    ]
