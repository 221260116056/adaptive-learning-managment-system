import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from django.conf import settings

url = settings.MOODLE_URL.replace('server.php', 'server.php')
params = {
    'wstoken': settings.MOODLE_TOKEN,
    'wsfunction': 'mod_page_get_pages_by_courses',
    'moodlewsrestformat': 'json',
    'courseids[0]': 5
}
resp = requests.post(url, data=params)
print(resp.text[:2000])
