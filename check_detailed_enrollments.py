import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.models import Enrollment, User

def check_all_enrollments():
    users = User.objects.filter(username='himansu')
    if users.exists():
        user = users.first()
        enrollments = Enrollment.objects.filter(student=user)
        print(f"User ID: {user.id}, Username: {user.username}")
        for e in enrollments:
            print(f"Enrollment ID: {e.id}, Course ID: {e.course_id}, Course Title: {e.course.title}, Paid: {e.is_paid}")
    else:
        print("User not found.")

if __name__ == "__main__":
    check_all_enrollments()
