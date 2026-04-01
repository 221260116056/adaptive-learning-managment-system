import requests
from django.conf import settings

class MoodleService:
    def __init__(self):
        self.token = settings.MOODLE_TOKEN
        self.url = settings.MOODLE_URL

    def _call(self, wsfunction, params={}):
        """Base method to call Moodle Web Services"""
        data = {
            'wstoken': self.token,
            'moodlewsrestformat': 'json',
            'wsfunction': wsfunction,
            **params
        }
        try:
            response = requests.post(self.url, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}

    def get_courses(self):
        """Fetch all courses (core_course_get_courses)"""
        return self._call('core_course_get_courses')

    def get_enrolled_users(self, course_id):
        """Fetch users in a course (core_enrol_get_enrolled_users)"""
        return self._call('core_enrol_get_enrolled_users', {'courseid': course_id})

    def get_user_by_field(self, field, value):
        """Fetch user by field (core_user_get_users_by_field)"""
        return self._call('core_user_get_users_by_field', {
            'field': field,
            'values[0]': value
        })
