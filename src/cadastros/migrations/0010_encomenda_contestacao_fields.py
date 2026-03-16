import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0009_ocorrencia_reabertura_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="encomenda",
            name="contestacao_observacao",
            field=models.TextField(
                blank=True,
                help_text="Observação do morador ao contestar o recebimento",
                null=True,
                verbose_name="Observação da Contestação",
            ),
        ),
        migrations.AddField(
            model_name="encomenda",
            name="contestado_em",
            field=models.DateTimeField(
                blank=True,
                help_text="Data e hora da contestação de recebimento",
                null=True,
                verbose_name="Contestado em",
            ),
        ),
        migrations.AddField(
            model_name="encomenda",
            name="contestado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="encomendas_contestadas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Contestado por",
            ),
        ),
        migrations.AddField(
            model_name="encomenda",
            name="contestacao_resolvida",
            field=models.BooleanField(
                default=False, verbose_name="Contestação resolvida"
            ),
        ),
    ]
