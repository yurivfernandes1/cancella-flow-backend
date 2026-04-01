from django.db import migrations


def create_event_user_groups(apps, _schema_editor):
    Group = apps.get_model("auth", "Group")

    group_names = [
        "Cerimonialista",
        "Recepção",
        "Organizador do Evento",
    ]

    for name in group_names:
        Group.objects.get_or_create(name=name)


def reverse_create_event_user_groups(apps, _schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(
        name__in=[
            "Cerimonialista",
            "Recepção",
            "Organizador do Evento",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("access", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_event_user_groups,
            reverse_create_event_user_groups,
        ),
    ]
