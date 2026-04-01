import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class MoodleTeacherManager:
    def __init__(self):
        self.token = settings.MOODLE_TOKEN
        self.url = settings.MOODLE_URL

    def _call(self, wsfunction, params={}):
        data = {
            'wstoken': self.token,
            'moodlewsrestformat': 'json',
            'wsfunction': wsfunction,
            **params
        }
        try:
            response = requests.post(self.url, data=data)
            response.raise_for_status()
            result = response.json()
            if isinstance(result, dict) and result.get('exception'):
                logger.error(f"Moodle Error ({wsfunction}): {result.get('message')}")
                return {'error': result.get('message')}
            return result
        except Exception as e:
            logger.error(f"Moodle Request Failed ({wsfunction}): {e}")
            return {'error': str(e)}

    def create_course(self, full_name, short_name, category_id=1, visible=1, start_date=None):
        """Creates a course in Moodle. Returns {'id': <course_id>} or {'error': <message>}."""
        params = {
            'courses[0][fullname]': full_name,
            'courses[0][shortname]': short_name,
            'courses[0][categoryid]': category_id,
            'courses[0][visible]': visible,
        }
        if start_date:
            params['courses[0][startdate]'] = int(start_date.timestamp())
        
        result = self._call('core_course_create_courses', params)
        if isinstance(result, list) and len(result) > 0:
            return {'id': result[0]['id']}
        if isinstance(result, dict) and result.get('error'):
            return result
        return {'error': 'Unknown Moodle course creation error'}

    def get_categories(self):
        """Fetch course categories for the dropdown."""
        return self._call('core_course_get_categories')

    def create_page(self, courseid, section, title, content):
        """Creates a 'page' resource using core_course_create_modules."""
        return self.create_module(courseid, section, title, 'page', {
            'content': content,
            'intro': title,
            'contentformat': 1 # HTML
        })

    def create_section(self, course_id, section_number, name):
        """Creates or updates a course section in Moodle."""
        params = {
            'courseid': course_id,
            'sections[0][number]': section_number,
            'sections[0][name]': name,
        }
        return self._call('core_course_create_sections', params)

    def create_module(self, course_id, section_number, module_name, module_type, cmid_params={}):
        """
        Creates a module (activity/resource) in Moodle using core_course_create_modules if available,
        falling back to specific creators if not.
        """
        params = {
            'courseid': course_id,
            'section': section_number,
            'module': module_type,
            'name': module_name,
            **cmid_params
        }
        return self._call('core_course_create_modules', params)

    def create_url(self, courseid, section, title, externalurl):
        """Standard way to add a URL resource."""
        params = {
            'courseid': courseid,
            'section': section,
            'name': title,
            'externalurl': externalurl,
            'display': 0, # Automatic
        }
        # Note: If core_course_create_modules is missing, this might need a specific plugin function
        # But for now we try the user-requested core_course_create_modules logic via a generic param
        return self.create_module(courseid, section, title, 'url', {'externalurl': externalurl})

    def get_enrolled_users(self, course_id):
        """Fetch users in a course."""
        return self._call('core_enrol_get_enrolled_users', {'courseid': course_id})

    def create_quiz(self, course_id, section_id, title):
        """Creates a quiz in Moodle using core_course_create_modules."""
        return self.create_module(course_id, section_id, title, 'quiz', {
            'intro': f"Quiz for {title}"
        })

    def get_course_contents(self, course_id):
        """Fetch course structure/sections from Moodle."""
        return self._call('core_course_get_contents', {'courseid': course_id})

    def delete_course(self, moodle_course_id):
        """Delete a course in Moodle by its Moodle course ID."""
        result = self._call('core_course_delete_courses', {
            'courseids[0]': moodle_course_id,
        })
        # Returns None on success, or a dict with 'error'
        if isinstance(result, dict) and result.get('error'):
            return {'error': result['error']}
        return {'success': True}

    def update_course_visibility(self, moodle_course_id, visible):
        """Hide/show a course in Moodle (visible = 1 or 0)."""
        result = self._call('core_course_update_courses', {
            'courses[0][id]': moodle_course_id,
            'courses[0][visible]': 1 if visible else 0,
        })
        if isinstance(result, dict) and result.get('error'):
            return {'error': result['error']}
        return {'success': True}
