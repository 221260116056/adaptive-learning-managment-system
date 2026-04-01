import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.moodle_sync import get_course_contents

def inspect_moodle_course():
    contents = get_course_contents(5)
    for s_idx, section in enumerate(contents):
        for m_idx, m_module in enumerate(section.get('modules', [])):
            if m_module.get('name') == 'python basic':
                with open('python_basic.json', 'w', encoding='utf-8') as f:
                    json.dump(m_module, f, indent=2)

if __name__ == "__main__":
    inspect_moodle_course()
