import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.models import Notification, Module

for n in Notification.objects.filter(link__isnull=True):
    if 'assignment' in n.message.lower():
        # Try to find the first assignment module
        m = Module.objects.filter(type='assignment').first()
        if m:
            n.link = f'/player/module/{m.id}/'
            n.save()
    elif 'certificate' in n.message.lower():
        n.link = '/certificates/'
        n.save()

print("Backfilled existing notifications.")
