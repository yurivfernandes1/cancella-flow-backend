from django.db import migrations, models


def forwards_func(apps, schema_editor):
    Evento = apps.get_model("cadastros", "Evento")
    # Tentar copiar valores existentes de data_evento/hora_* para datetime_inicio/fim
    for ev in Evento.objects.all():
        try:
            if hasattr(ev, "data_evento") and hasattr(ev, "hora_inicio"):
                from datetime import datetime

                from django.utils import timezone

                if ev.data_evento and ev.hora_inicio:
                    ev.datetime_inicio = timezone.make_aware(
                        datetime.combine(ev.data_evento, ev.hora_inicio)
                    )
                if ev.data_evento and hasattr(ev, "hora_fim") and ev.hora_fim:
                    ev.datetime_fim = timezone.make_aware(
                        datetime.combine(ev.data_evento, ev.hora_fim)
                    )
                ev.save(update_fields=["datetime_inicio", "datetime_fim"])
        except Exception:
            pass


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0009_evento"),
    ]

    operations = [
        migrations.AddField(
            model_name="evento",
            name="datetime_inicio",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Início",
                help_text="Data e hora de início do evento",
            ),
        ),
        migrations.AddField(
            model_name="evento",
            name="datetime_fim",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Término",
                help_text="Data e hora de término do evento",
            ),
        ),
        migrations.RunPython(forwards_func, migrations.RunPython.noop),
        # Opcionalmente poderíamos remover campos antigos em uma migração futura
    ]
