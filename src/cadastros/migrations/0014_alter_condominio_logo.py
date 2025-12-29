import app.utils.image_validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "cadastros",
            "0013_remove_condominio_endereco_condominio_cep_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="condominio",
            name="logo",
            field=models.FileField(
                upload_to="logos/",
                null=True,
                blank=True,
                validators=[app.utils.image_validators.validate_logo_file],
                help_text="Logo quadrada até 250x250px (png, jpg, jpeg, svg)",
            ),
        ),
    ]
