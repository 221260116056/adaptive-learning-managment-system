import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from django.conf import settings
from student.models import Module

m = Module.objects.get(id=17)
print("URL:", m.video_url)
resp = requests.get(m.video_url)
print("Status:", resp.status_code)
print("Content:", resp.text)
