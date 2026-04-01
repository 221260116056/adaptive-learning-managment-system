import json

with open('module_json.txt', 'r', encoding='utf-8') as f:
    text = f.read()
    # Strip DEBUG lines from the top
    lines = text.split('\n')
    json_lines = [l for l in lines if not l.startswith('DEBUG')]
    try:
        data = json.loads('\n'.join(json_lines))
        import pprint
        pprint.pprint(data)
    except Exception as e:
        print("Error parsing json:", e)
        print(text[:500])
