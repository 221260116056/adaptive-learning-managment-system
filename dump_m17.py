import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.moodle_sync import get_course_contents

contents = get_course_contents(5)
for section in contents:
    for m in section.get('modules', []):
        name = m.get('name')
        if 'syntax' in name.lower():
            with open('module_17.json', 'w', encoding='utf-8') as f:
                json.dump(m, f, indent=2)
                
