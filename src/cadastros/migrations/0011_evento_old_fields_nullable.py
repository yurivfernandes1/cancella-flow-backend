from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0010_evento_datetime_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evento",
            name="data_evento",
            field=models.DateField(
                null=True,
                blank=True,
                verbose_name="Data do Evento",
                help_text="Data em que o evento acontecerá",
            ),
        ),
        migrations.AlterField(
            model_name="evento",
            name="hora_inicio",
            field=models.TimeField(
                null=True,
                blank=True,
                verbose_name="Hora de Início",
                help_text="Hora de início do evento",
            ),
        ),
        migrations.AlterField(
            model_name="evento",
            name="hora_fim",
            field=models.TimeField(
                null=True,
                blank=True,
                verbose_name="Hora de Término",
                help_text="Hora de término do evento",
            ),
        ),
    ]
