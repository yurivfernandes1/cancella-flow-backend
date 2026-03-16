import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0008_visitante_email_qr_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="ocorrencia",
            name="motivo_reabertura",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ocorrencia",
            name="reaberto_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ocorrencia",
            name="reaberto_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ocorrencias_reabertas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
