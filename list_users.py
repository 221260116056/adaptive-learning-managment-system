import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from django.contrib.auth.models import User

def check_users():
    users = User.objects.all()
    print("--- All Users ---")
    for u in users:
        print(f"ID: {u.id}, Username: {u.username}, Email: {u.email}")

if __name__ == "__main__":
    check_users()
