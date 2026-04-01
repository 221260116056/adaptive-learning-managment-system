import requests
import json

MOODLE_URL = 'http://localhost/moodle/webservice/rest/server.php'
MOODLE_TOKEN = '7d330c0700a5e224213aec6e239e3b84'

def test_moodle_connection():
    print(f"Testing Moodle connection to {MOODLE_URL}")
    params = {
        'wstoken': MOODLE_TOKEN,
        'wsfunction': 'core_user_get_users_by_field',
        'moodlewsrestformat': 'json',
        'field': 'email',
        'values[0]': 'himansu123@gmail.com'
    }
    
    try:
        response = requests.post(MOODLE_URL, data=params)
        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"User Search Result: {json.dumps(result, indent=2)}")
        
        if isinstance(result, list) and len(result) > 0:
            user_id = result[0]['id']
            print(f"User ID found: {user_id}")
            
            # Now test course fetching
            params_courses = {
                'wstoken': MOODLE_TOKEN,
                'wsfunction': 'core_enrol_get_users_courses',
                'moodlewsrestformat': 'json',
                'userid': user_id
            }
            response_courses = requests.post(MOODLE_URL, data=params_courses)
            courses_result = response_courses.json()
            print(f"Courses Result: {json.dumps(courses_result, indent=2)}")
        else:
            print("User not found by email. Trying username 'himansu'...")
            params['field'] = 'username'
            params['values[0]'] = 'himansu'
            response = requests.post(MOODLE_URL, data=params)
            result = response.json()
            print(f"Username Search Result: {json.dumps(result, indent=2)}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_moodle_connection()
