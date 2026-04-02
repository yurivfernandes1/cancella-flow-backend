from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0005_convidadolistacerimonial_created_by"),
    ]

    operations = [
        migrations.AlterField(
            model_name="convidadolistacerimonial",
            name="cpf",
            field=models.CharField(
                blank=True,
                max_length=11,
                null=True,
                verbose_name="CPF",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="convidadolistacerimonial",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="convidadolistacerimonial",
            constraint=models.UniqueConstraint(
                condition=models.Q(cpf__isnull=False) & ~models.Q(cpf=""),
                fields=("lista", "cpf"),
                name="cad_cer_lista_cpf_unique_if_present",
            ),
        ),
    ]
