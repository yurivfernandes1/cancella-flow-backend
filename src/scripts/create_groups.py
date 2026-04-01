import os
import sys
from pathlib import Path

# Ensure project src directory is in sys.path so 'app' settings module can be imported
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

from django.contrib.auth.models import Group

GROUP_NAMES = [
    "admin",
    "Síndicos",
    "Portaria",
    "Moradores",
    "Cerimonialista",
    "Recepção",
    "Organizador do Evento",
]

for name in GROUP_NAMES:
    g, created = Group.objects.get_or_create(name=name)
    print("Group '{}': {}".format(name, "created" if created else "exists"))
