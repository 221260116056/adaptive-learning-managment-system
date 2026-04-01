import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.models import Module

def check_module_url():
    try:
        m = Module.objects.get(id=1)
        print(f"Module ID: 1")
        print(f"Title: {m.title}")
        print(f"Video URL: {m.video_url}")
    except Module.DoesNotExist:
        print("Module 1 not found.")

if __name__ == "__main__":
    check_module_url()
