import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.models import StudentProfile, User

def check_profiles():
    users = User.objects.filter(username='himansu')
    if users.exists():
        user = users.first()
        profile, _ = StudentProfile.objects.get_or_create(user=user)
        print(f"User: {user.username}, Email: {user.email}")
        print(f"Moodle User ID in Django: {profile.moodle_user_id}")
    else:
        print("User 'himansu' not found in Django.")

if __name__ == "__main__":
    check_profiles()
