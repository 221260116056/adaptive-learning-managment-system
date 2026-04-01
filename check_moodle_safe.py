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
            if m_module.get('modname') in ['resource', 'video', 'url', 'page']:
                s = f"[{s_idx}-{m_idx}] {m_module.get('name')} | Type: {m_module.get('modname')}"
                if 'url' in m_module:
                    s += f" | URL: {m_module['url']}"
                if 'contents' in m_module:
                    for c in m_module['contents']:
                        s += f" | Content URL: {c.get('fileurl')} (Mtype: {c.get('mimetype')})"
                # encode as ascii to avoid powershell truncating issues
                print(s.encode('ascii', errors='ignore').decode('ascii'))

if __name__ == "__main__":
    inspect_moodle_course()
