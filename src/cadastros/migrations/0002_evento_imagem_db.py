from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="evento",
            name="imagem_db_data",
            field=models.BinaryField(
                blank=True,
                null=True,
                help_text="Dados binários da imagem armazenados no banco",
            ),
        ),
        migrations.AddField(
            model_name="evento",
            name="imagem_db_content_type",
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                help_text="Content-Type do arquivo de imagem",
            ),
        ),
        migrations.AddField(
            model_name="evento",
            name="imagem_db_filename",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                help_text="Nome original do arquivo de imagem",
            ),
        ),
        migrations.AlterField(
            model_name="evento",
            name="imagem",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="eventos/",
                verbose_name="Imagem",
                help_text="Imagem ilustrativa do evento (legado — prefer imagem_db)",
            ),
        ),
    ]
