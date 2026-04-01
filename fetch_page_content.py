import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from django.conf import settings
from student.models import Module

m = Module.objects.get(id=17)
print("URL:", m.video_url)
resp = requests.post(m.video_url, data={'token': settings.MOODLE_TOKEN})
print("Using POST with token, Status:", resp.status_code)

if resp.json().get('error'):
    url_with_token = m.video_url + f"&token={settings.MOODLE_TOKEN}"
    resp = requests.get(url_with_token)
    print("Using GET with token, Status:", resp.status_code)

print("Content preview:")
try:
    print(resp.text[:500])
except UnicodeEncodeError:
    print(resp.text[:500].encode('ascii', 'ignore').decode('ascii'))
