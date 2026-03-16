import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0010_encomenda_contestacao_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="encomenda",
            name="contestacao_resposta",
            field=models.TextField(
                blank=True,
                help_text="Resposta do síndico para o morador sobre a contestação",
                null=True,
                verbose_name="Resposta da Contestação",
            ),
        ),
        migrations.AddField(
            model_name="encomenda",
            name="contestacao_respondido_em",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Contestação respondida em",
            ),
        ),
        migrations.AddField(
            model_name="encomenda",
            name="contestacao_respondido_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="encomendas_contestacoes_respondidas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Contestação respondida por",
            ),
        ),
    ]
