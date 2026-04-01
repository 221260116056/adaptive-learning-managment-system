import subprocess, os

test_input = r"C:\Python Vraj\Adaptive Learning management system\media\videos\raw\856787-hd_1920_1080_30fps_-_Copy_E4MexiR.mp4"
test_output = r"C:\Python Vraj\Adaptive Learning management system\media\videos\dash\test_ffmpeg\manifest.mpd"

os.makedirs(os.path.dirname(test_output), exist_ok=True)

command = [
    "ffmpeg",
    "-y",
    "-i", test_input,

    "-map", "0:v:0",
    "-map", "0:a?",

    "-c:v", "libx264",
    "-preset", "veryfast",
    "-crf", "23",

    "-c:a", "aac",
    "-b:a", "128k",

    "-b:v:0", "150k", "-s:v:0", "256x144",
    "-b:v:1", "300k", "-s:v:1", "426x240",
    "-b:v:2", "800k", "-s:v:2", "640x360",
    "-b:v:3", "1400k", "-s:v:3", "842x480",
    "-b:v:4", "2800k", "-s:v:4", "1280x720",
    "-b:v:5", "5000k", "-s:v:5", "1920x1080",

    "-use_timeline", "1",
    "-use_template", "1",

    "-adaptation_sets", "id=0,streams=v id=1,streams=a",

    "-f", "dash",
    test_output
]

result = subprocess.run(command, capture_output=True, text=True)
if result.returncode != 0:
    print("FAILED")
    print("STDERR:")
    print(result.stderr)
else:
    print("SUCCESS")
