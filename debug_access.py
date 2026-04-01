import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()
from django.contrib.auth.models import User
from student.models import Enrollment, Module
user = User.objects.get(username='dhruv')
out = []
for m_id in [59, 61]:
    try:
        m = Module.objects.get(id=m_id)
        is_enrolled = Enrollment.objects.filter(student=user, course=m.course).exists()
        is_teacher = m.course.teacher_id == user.id
        out.append(f'Module {m_id} -> Course {m.course.id} ({m.course.title}) | Teacher ID: {m.course.teacher_id} | User ID: {user.id}')
        out.append(f'  is_enrolled: {is_enrolled}, is_teacher: {is_teacher}, is_superuser: {user.is_superuser}')
    except Exception as e:
        out.append(f'Module {m_id} error: {e}')

with open('debug_access_out.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
