import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.models import Course, Module

print("Starting to backfill module orders...")
courses = Course.objects.all()
for course in courses:
    # order by 'id' to get creation sequence
    modules = Module.objects.filter(course=course).order_by('id')
    for idx, module in enumerate(modules, start=1):
        module.order = idx
        # Avoiding full save() to bypass newly added Max('order') logic, since we explicitly provide it
        module.save(update_fields=['order'])
        print(f"Course {course.id}: Module '{module.title}' (ID {module.id}) -> Order {idx}")

print("Backfill completed.")
