import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.moodle_sync import get_course_contents

def inspect_moodle_course():
    contents = get_course_contents(5)
    with open('moodle_check_log.txt', 'w') as f:
        for s_idx, section in enumerate(contents):
            for m_idx, m_module in enumerate(section.get('modules', [])):
                if m_module.get('modname') in ['resource', 'video', 'url', 'page']:
                    f.write(f"--- Section {s_idx}, Module {m_idx} ---\n")
                    f.write(f"Name: {m_module.get('name')}\n")
                    f.write(f"Modname: {m_module.get('modname')}\n")
                    if 'url' in m_module:
                        f.write(f"URL: {m_module['url']}\n")
                    if 'contents' in m_module:
                        for c in m_module['contents']:
                            f.write(f"Content FileURL: {c.get('fileurl')}\n")
                            f.write(f"Content Mimetype: {c.get('mimetype')}\n")

if __name__ == "__main__":
    inspect_moodle_course()
