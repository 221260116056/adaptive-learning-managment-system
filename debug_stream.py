import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()
from django.test import RequestFactory
from django.contrib.auth.models import User
from student.views import stream_dash_video

user = User.objects.get(username='dhruv')
factory = RequestFactory()
request = factory.get('/stream/61/manifest.mpd')
request.user = user

try:
    response = stream_dash_video(request, 61, 'manifest.mpd')
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.get('Content-Type')}")
    if response.status_code == 200:
        print("Success! File can be streamed.")
    else:
        print(f"Content: {response.content}")
except Exception as e:
    print(f"Exception: {e}")
