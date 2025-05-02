# sync_video_with_tts.py

import os
import subprocess

from gtts import gTTS


def get_duration(path):
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path
    ], capture_output=True, text=True)
    return float(result.stdout.strip())

def sync_video_with_tts(run_dir: str):
    prompt_path = os.path.join(run_dir, "story_prompt.txt")
    with open(prompt_path) as f:
        story = f.read().strip()

    tts_audio = os.path.join(run_dir, "story_audio.mp3")
    gTTS(story, lang="en").save(tts_audio)
    print(f"TTS saved: {tts_audio}")

    input_video = os.path.join(run_dir, "output_story_video.mp4")
    temp_video = os.path.join(run_dir, "temp_adjusted_video.mp4")
    final_video = os.path.join(run_dir, "final_story_video.mp4")

    v_dur = get_duration(input_video)
    a_dur = get_duration(tts_audio)
    speed = v_dur / a_dur

    # Adjust video speed to match audio duration
    os.system(
        f'ffmpeg -y -i "{input_video}" '
        f'-filter_complex "[0:v]setpts={1/speed}*PTS[v]" '
        f'-map "[v]" -an "{temp_video}"'
    )
    # Combine adjusted video with audio
    os.system(
        f'ffmpeg -y -i "{temp_video}" -i "{tts_audio}" '
        f'-c:v copy -c:a aac -shortest "{final_video}"'
    )
    print(f"Final video saved: {final_video}")
