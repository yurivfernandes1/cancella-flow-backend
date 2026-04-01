from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0004_convidadolistacerimonial_resposta_presenca"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="convidadolistacerimonial",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="convidados_cerimonial_criados",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
