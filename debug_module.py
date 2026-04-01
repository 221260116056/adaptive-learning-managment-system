import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from django.conf import settings
from student.models import Module

m = Module.objects.get(id=59)

# Read the full MPD
mpd_path = os.path.join(settings.MEDIA_ROOT, m.dash_manifest)
with open(mpd_path, 'r') as f:
    content = f.read()

with open('debug_mpd.txt', 'w') as f:
    f.write(content)

print("MPD written to debug_mpd.txt")
print(f"dash_manifest value stored: {repr(m.dash_manifest)}")
print(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
print(f"MEDIA_URL: {settings.MEDIA_URL}")
