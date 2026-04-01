import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learntrust.settings')
django.setup()

from student.moodle_sync import get_course_contents
from student.models import Course, Module
from django.conf import settings

def force_sync_modules():
    courses = Course.objects.all()
    for course in courses:
        if course.moodle_course_id:
            print(f"Syncing course: {course.title} (Moodle ID: {course.moodle_course_id})")
            contents = get_course_contents(course.moodle_course_id)
            for section_idx, section in enumerate(contents):
                for m_module in section.get('modules', []):
                    if m_module.get('modname') in ['resource', 'video', 'url', 'page']:
                        m_url = ""
                        if m_module.get('contents'):
                            for c in m_module['contents']:
                                if 'video' in c.get('mimetype', '') or c.get('filename', '').endswith(('.mp4', '.webm', '.ogg')):
                                    m_url = c.get('fileurl', '')
                                    m_url = m_url.replace('forcedownload=1', 'forcedownload=0')
                                    if m_url and 'token=' not in m_url:
                                        sep = '&' if '?' in m_url else '?'
                                        m_url += f"{sep}token={settings.MOODLE_TOKEN}"
                                    break
                        
                        if not m_url and m_module.get('url'):
                            m_url = m_module['url']
                        
                        mod, created = Module.objects.update_or_create(
                            course=course,
                            title=m_module.get('name', 'Untitled Module'),
                            defaults={
                                'description': m_module.get('description', ''),
                                'order': section_idx * 100 + m_module.get('id', 0),
                                'video_url': m_url,
                                'is_published': True
                            }
                        )
                        print(f"  [{'CREATED' if created else 'UPDATED'}] {mod.title} -> {mod.video_url}")

if __name__ == "__main__":
    force_sync_modules()
