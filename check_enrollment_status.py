import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.models import Enrollment, User

def check_unpaid():
    users = User.objects.filter(username='himansu')
    if users.exists():
        user = users.first()
        enrollments = Enrollment.objects.filter(student=user)
        print(f"User: {user.username}")
        for e in enrollments:
            print(f"Course: {e.course.title}, Paid: {e.is_paid}")
    else:
        print("User not found.")

if __name__ == "__main__":
    check_unpaid()
