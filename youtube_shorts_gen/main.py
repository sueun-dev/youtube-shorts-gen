import os
import time
from datetime import datetime

from runway import generate_video
from sync_video_with_tts import sync_video_with_tts
from upload_to_youtube import upload_video
from youtube_script_gen import generate_story_and_image


def run_pipeline_once():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = os.path.join("runs", timestamp)
    os.makedirs(run_dir, exist_ok=True)

    print(f"\n[START] New Run: {run_dir}")
    generate_story_and_image(run_dir)
    generate_video(run_dir)
    sync_video_with_tts(run_dir)
    upload_video(run_dir)
    print(f"[DONE] Uploaded: {run_dir}\n")

if __name__ == "__main__":
    while True:
        run_pipeline_once()
        print("Waiting 10 minutes until next run...")
        time.sleep(600)
