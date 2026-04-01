import requests
import json

MOODLE_URL = 'http://localhost/moodle/webservice/rest/server.php'
MOODLE_TOKEN = '7d330c0700a5e224213aec6e239e3b84'

def test_moodle_info():
    params = {
        'wstoken': MOODLE_TOKEN,
        'wsfunction': 'core_webservice_get_site_info',
        'moodlewsrestformat': 'json',
    }
    try:
        response = requests.post(MOODLE_URL, data=params)
        print(f"Site Info: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_moodle_info()
