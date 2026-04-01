import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.models import Module, StudentProgress, WatchEvent

print("Deleting all existing modules, progress, and watch events specifically for course sync cleanup...")
WatchEvent.objects.all().delete()
StudentProgress.objects.all().delete()
Module.objects.all().delete()
print("Done. Now re-running force_sync.py logic...")

import force_sync
force_sync.force_sync_modules()
print("Cleanup complete!")
