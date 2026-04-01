import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.models import Enrollment, User, Course

def check_enrollments():
    print("--- Enrollments for 'himansu' ---")
    users = User.objects.filter(username='himansu')
    if users.exists():
        user = users.first()
        enrollments = Enrollment.objects.filter(student=user)
        print(f"Total enrollments: {enrollments.count()}")
        for e in enrollments:
            print(f"Course: {e.course.title}, Paid: {e.is_paid}, Moodle ID: {e.course.moodle_course_id}")
    else:
        print("User 'himansu' not found.")

if __name__ == "__main__":
    check_enrollments()
