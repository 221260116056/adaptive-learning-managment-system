import requests
import logging
from django.conf import settings
from .models import StudentProfile

logger = logging.getLogger(__name__)

def get_moodle_user(email, username=None):
    """
    Check if the user exists in Moodle using core_user_get_users_by_field.
    Tries email first, then username.
    """
    print(f"DEBUG: Fetching Moodle user for email: {email}")
    params = {
        'wstoken': settings.MOODLE_TOKEN,
        'wsfunction': 'core_user_get_users_by_field',
        'moodlewsrestformat': 'json',
        'field': 'email',
        'values[0]': email
    }
    
    try:
        response = requests.post(settings.MOODLE_URL, data=params)
        response.raise_for_status()
        result = response.json()
        
        if isinstance(result, dict) and result.get('exception'):
            print(f"DEBUG: Moodle API Exception: {result.get('message')}")
            return None
        
        if isinstance(result, list) and len(result) > 0:
            print("DEBUG: Moodle user found by email")
            return result[0]
        
        if username:
            print(f"DEBUG: Email not found, trying username: {username}")
            params['field'] = 'username'
            params['values[0]'] = username.lower()
            response = requests.post(settings.MOODLE_URL, data=params)
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                print("DEBUG: Moodle user found by username")
                return result[0]
                
        return None
    except Exception as e:
        print(f"DEBUG: Error fetching Moodle user: {e}")
        return None


def create_moodle_user(username, email, password, firstname="Student", lastname="User"):
    """
    Create a new Moodle user using core_user_create_users.
    """
    print(f"DEBUG: Creating Moodle user: {username}")
    params = {
        'wstoken': settings.MOODLE_TOKEN,
        'wsfunction': 'core_user_create_users',
        'moodlewsrestformat': 'json',
        'users[0][username]': username.lower(),
        'users[0][email]': email,
        'users[0][password]': password,
        'users[0][firstname]': firstname,
        'users[0][lastname]': lastname,
    }
    
    try:
        response = requests.post(settings.MOODLE_URL, data=params)
        response.raise_for_status()
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0:
            print("DEBUG: Moodle user created successfully")
            return result[0] # Returns {'id': 123, 'username': '...'}
        else:
            print(f"DEBUG: Moodle creation error: {result}")
            return None
    except Exception as e:
        print(f"DEBUG: Error creating Moodle user: {e}")
        return None

def sync_moodle_user(django_user, password=None):
    """
    Synchronizes a Django user with Moodle.
    Called during login or registration.
    """
    # 1. First check if user already has a Moodle ID in their profile
    profile, created = StudentProfile.objects.get_or_create(user=django_user)
    
    # 2. Check Moodle by email or username
    moodle_user = get_moodle_user(django_user.email, django_user.username)
    
    if moodle_user:
        # User exists in Moodle, update profile
        profile.moodle_user_id = moodle_user['id']
        profile.save()
        return moodle_user['id']

    else:
        # 3. If not found, create the user
        # Note: Moodle passwords often require complex characters (1 digit, 1 lower, 1 upper, 1 non-alphanumeric)
        # If password is matched from registration, use it. Otherwise, use a default secure one if needed.
        moodle_password = password if password else "Moodle@123456" 
        
        new_moodle_user = create_moodle_user(
            username=django_user.username,
            email=django_user.email,
            password=moodle_password,
            firstname=django_user.first_name if django_user.first_name else django_user.username,
            lastname=django_user.last_name if django_user.last_name else "User"
        )
        
        if new_moodle_user:
            profile.moodle_user_id = new_moodle_user['id']
            profile.save()
            return new_moodle_user['id']
            
def get_moodle_courses(moodle_user_id):
    """
    Fetch enrolled courses for a specific Moodle user using core_enrol_get_users_courses.
    """
    print(f"DEBUG: Fetching Moodle courses")
    params = {
        'wstoken': settings.MOODLE_TOKEN,
        'wsfunction': 'core_enrol_get_users_courses',
        'moodlewsrestformat': 'json',
        'userid': moodle_user_id
    }
    
    try:
        response = requests.post(settings.MOODLE_URL, data=params)
        response.raise_for_status()
        result = response.json()
        # print(f"DEBUG: Moodle API response: {result}") # Commented out to avoid encoding issues
        
        if isinstance(result, dict) and result.get('exception'):
            print(f"DEBUG: Moodle API Exception: {result.get('message')}")
            return None

        
        if isinstance(result, list):
            print(f"DEBUG: Courses found: {len(result)}")
            return result
        return []
    except Exception as e:
        print(f"DEBUG: Error fetching Moodle courses: {e}")
        return []

def get_course_contents(course_id):
    """
    Fetch course contents (sections and modules) from Moodle using core_course_get_contents.
    """
    print(f"DEBUG: Fetching Moodle course contents for course ID: {course_id}")
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
        
        if isinstance(result, dict) and result.get('exception'):
            print(f"DEBUG: Moodle API Exception: {result.get('message')}")
            return []
            
        return result
    except Exception as e:
        print(f"DEBUG: Error fetching course contents: {e}")
        return []

def enrol_user_in_course(moodle_user_id, moodle_course_id):
    """
    Manually enroll a user in a Moodle course.
    """
    print(f"DEBUG: Enrolling Moodle user {moodle_user_id} in course {moodle_course_id}")
    params = {
        'wstoken': settings.MOODLE_TOKEN,
        'wsfunction': 'enrol_manual_enrol_users',
        'moodlewsrestformat': 'json',
        'enrolments[0][roleid]': 5, # Student role
        'enrolments[0][userid]': moodle_user_id,
        'enrolments[0][courseid]': moodle_course_id,
    }
    
    try:
        response = requests.post(settings.MOODLE_URL, data=params)
        response.raise_for_status()
        result = response.json()
        
        # This function usually returns null/None on success in REST if no exception happened
        if result is None:
            print("DEBUG: User enrolled in Moodle successfully")
            return True
        elif isinstance(result, dict) and result.get('exception'):
            print(f"DEBUG: Moodle Enrollment Error: {result.get('message')}")
            return False
        return True
    except Exception as e:
        print(f"DEBUG: Error enrolling user in Moodle: {e}")
        return False
