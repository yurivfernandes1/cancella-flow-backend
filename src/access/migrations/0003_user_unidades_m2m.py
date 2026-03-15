from django.db import migrations, models


def migrate_unidade_to_unidades(apps, schema_editor):
    """Copia o FK unidade → M2M unidades para cada usuário."""
    User = apps.get_model("access", "User")
    for user in User.objects.filter(unidade__isnull=False).select_related(
        "unidade"
    ):
        user.unidades.add(user.unidade)


class Migration(migrations.Migration):
    dependencies = [
        ("access", "0002_initial"),
        ("cadastros", "0001_initial"),
    ]

    operations = [
        # 1. Criar a tabela M2M
        migrations.AddField(
            model_name="user",
            name="unidades",
            field=models.ManyToManyField(
                blank=True,
                help_text="Unidades onde o morador reside",
                related_name="moradores",
                to="cadastros.unidade",
                verbose_name="Unidades",
            ),
        ),
        # 2. Migrar dados existentes do FK para o M2M
        migrations.RunPython(
            migrate_unidade_to_unidades,
            migrations.RunPython.noop,
        ),
        # 3. Remover o FK antigo
        migrations.RemoveField(
            model_name="user",
            name="unidade",
        ),
    ]
