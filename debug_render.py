import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()
from django.test import RequestFactory
from django.contrib.auth.models import User
from student.views import video_player

user = User.objects.get(username='dhruv')
factory = RequestFactory()
request = factory.get('/player/module/61/')
request.user = user

try:
    response = video_player(request, 61)
    with open('render_61.html', 'w', encoding='utf-8') as f:
        f.write(response.content.decode('utf-8'))
    print("Rendered HTML to render_61.html")
except Exception as e:
    print(f"Error rendering: {e}")
