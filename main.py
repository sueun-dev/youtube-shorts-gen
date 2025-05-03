import logging
import os
import time
from datetime import datetime

from youtube_shorts_gen.config import RUNS_BASE_DIR, SLEEP_SECONDS
from youtube_shorts_gen.runway import VideoGenerator
from youtube_shorts_gen.sync_video_with_tts import VideoAudioSyncer
from youtube_shorts_gen.upload_to_youtube import YouTubeUploader
from youtube_shorts_gen.youtube_script_gen import YouTubeScriptGenerator


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_pipeline_once():
    """Run a single end-to-end generation and upload pipeline."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = os.path.join(RUNS_BASE_DIR, timestamp)
    os.makedirs(run_dir, exist_ok=True)

    logging.info("[START] New Run: %s", run_dir)

    try:
        # 1. Generate story and image
        script_generator = YouTubeScriptGenerator(run_dir)
        script_generator.run()

        # 2. Generate video using Runway
        video_generator = VideoGenerator(run_dir)
        video_generator.generate()

        # 3. Sync video with TTS
        synchronizer = VideoAudioSyncer(run_dir)
        synchronizer.sync()

        # 4. Upload to YouTube (if credentials are available)
        uploader = YouTubeUploader(run_dir)
        video_url = uploader.upload()
        
        if video_url:
            logging.info("[DONE] Uploaded to YouTube: %s", video_url)
        else:
            logging.info("[DONE] Video created but not uploaded to YouTube: %s", 
                         os.path.join(run_dir, "final_story_video.mp4"))

        logging.info("[DONE] Pipeline completed for: %s", run_dir)
    except Exception as e:
        logging.exception("[ERROR] Pipeline failed: %s", e)


if __name__ == "__main__":
    setup_logging()

    while True:
        run_pipeline_once()
        logging.info("Waiting %d minutes until next run...", SLEEP_SECONDS // 60)
        time.sleep(SLEEP_SECONDS)
