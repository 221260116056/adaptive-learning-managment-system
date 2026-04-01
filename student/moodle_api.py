import requests
from django.conf import settings

def get_moodle_courses(user_id):
    """
    Fetch enrolled courses for a given Moodle user ID using core_enrol_get_users_courses.
    """
    print(f"DEBUG: Fetching Moodle courses")
    params = {
        'wstoken': settings.MOODLE_TOKEN,
        'wsfunction': 'core_enrol_get_users_courses',
        'moodlewsrestformat': 'json',
        'userid': user_id
    }
    try:
        response = requests.post(settings.MOODLE_URL, data=params)
        response.raise_for_status()
        result = response.json()
        print(f"DEBUG: Moodle API response")
        return result
    except Exception as e:
        print(f"DEBUG: Error fetching Moodle courses: {e}")
        return []

def get_course_modules(course_id):
    """
    Fetch course modules (sections) from Moodle using core_course_get_contents.
    """
    print(f"DEBUG: Fetching course modules")
    params = {
        'wstoken': settings.MOODLE_TOKEN,
        'wsfunction': 'core_course_get_contents',
        'moodlewsrestformat': 'json',
        'courseid': course_id
    }
    try:
        response = requests.post(settings.MOODLE_URL, data=params)
        response.raise_for_status()
        result = response.json()
        print(f"DEBUG: Moodle API response")
        return result
    except Exception as e:
        print(f"DEBUG: Error fetching course modules: {e}")
        return []

def get_module_content(module_id):
    """
    Fetch specific module details using core_course_get_module.
    Note: Returns a dictionary with 'cm' (course module) info.
    """
    print(f"DEBUG: Fetching module content")
    params = {
        'wstoken': settings.MOODLE_TOKEN,
        'wsfunction': 'core_course_get_module',
        'moodlewsrestformat': 'json',
        'id': module_id
    }
    try:
        response = requests.post(settings.MOODLE_URL, data=params)
        response.raise_for_status()
        result = response.json()
        print(f"DEBUG: Moodle API response")
        return result
    except Exception as e:
        print(f"DEBUG: Error fetching module content: {e}")
        return None
