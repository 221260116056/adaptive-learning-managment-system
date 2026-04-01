import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.models import Module

with open('db_modules.txt', 'w', encoding='utf-8') as f:
    for m in Module.objects.all():
        f.write(f"ID: {m.id} | Title: {m.title} | URL: {m.video_url[:100]}\n")
