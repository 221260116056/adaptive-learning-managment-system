import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.models import Module

for m in Module.objects.all():
    if "python" in m.title.lower():
        print(f"ID: {m.id} | Title: {m.title} | URL: {m.video_url}")
