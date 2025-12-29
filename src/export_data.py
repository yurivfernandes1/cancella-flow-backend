#!/usr/bin/env python
import os
import sys

# Define o banco como SQLite temporariamente
os.environ['DB_ENGINE'] = 'sqlite'

# Configura o Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
import django
django.setup()

from django.core.management import call_command

# Exporta os dados
print("Exportando dados do SQLite...")
with open('data_backup.json', 'w', encoding='utf-8') as f:
    call_command(
        'dumpdata',
        '--natural-foreign',
        '--natural-primary',
        '-e', 'contenttypes',
        '-e', 'auth.Permission',
        '--indent', '2',
        stdout=f
    )
print("✓ Dados exportados para data_backup.json")
