import uuid

from django.db import migrations, models


def populate_qr_tokens(apps, schema_editor):
    Visitante = apps.get_model('cadastros', 'Visitante')
    for visitante in Visitante.objects.all():
        visitante.qr_token = uuid.uuid4()
        visitante.save(update_fields=['qr_token'])


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0007_aviso_grupos_alter_aviso_grupo"),
    ]

    operations = [
        migrations.AddField(
            model_name="visitante",
            name="email",
            field=models.EmailField(
                blank=True,
                help_text="E-mail do visitante para envio do QR Code (opcional)",
                max_length=254,
                null=True,
                verbose_name="E-mail",
            ),
        ),
        # Adiciona o campo sem unique para poder preencher cada linha individualmente
        migrations.AddField(
            model_name="visitante",
            name="qr_token",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text="Token único utilizado para geração do QR Code de entrada",
                unique=False,
                verbose_name="Token QR",
            ),
        ),
        # Preenche UUIDs únicos para cada linha existente
        migrations.RunPython(populate_qr_tokens, migrations.RunPython.noop),
        # Adiciona o constraint unique
        migrations.AlterField(
            model_name="visitante",
            name="qr_token",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text="Token único utilizado para geração do QR Code de entrada",
                unique=True,
                verbose_name="Token QR",
            ),
        ),
    ]
