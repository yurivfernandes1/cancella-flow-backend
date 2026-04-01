from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0003_funcaofesta_eventocerimonialfuncionario_funcoes"),
    ]

    operations = [
        migrations.AddField(
            model_name="convidadolistacerimonial",
            name="resposta_presenca",
            field=models.CharField(
                choices=[
                    ("pendente", "Pendente"),
                    ("confirmado", "Confirmado"),
                    ("recusado", "Recusado"),
                ],
                default="pendente",
                max_length=10,
                verbose_name="Resposta de Presença",
            ),
        ),
        migrations.AddField(
            model_name="convidadolistacerimonial",
            name="resposta_presenca_em",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Respondido em",
            ),
        ),
    ]
