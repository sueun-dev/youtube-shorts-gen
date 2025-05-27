"""YouTube Shorts Generator Package."""

# Define what's exported when using wildcard imports
__all__ = [
    # Content module exports
    "InternetContentFetcher",
    "ScriptAndImageFromInternet",
    "ScriptAndImageGenerator",
    "generate_dynamic_prompt",
    # Media module exports
    "ParagraphProcessor",
    "ParagraphTTS",
    "ParagraphTTSSyncer",
    "VideoGenerator",
    "VideoAudioSyncer",
    "TTSGenerator",
    "NewVideoAudioSyncer",
    # Upload module exports
    "UploadHistory",
    "YouTubeUploader",
    # Config constants
    "ACTIONS",
    "ANIMALS",
    "BACKGROUNDS",
    "DANCES",
    "EMPTY_IMAGE_B64",
    "HUMANS",
    "IMAGE_PROMPT_TEMPLATE",
    "OPENAI_API_KEY",
    "OPENAI_CHAT_MODEL",
    "OPENAI_IMAGE_MODEL",
    "OPENAI_IMAGE_QUALITY",
    "OPENAI_IMAGE_SIZE",
    "RUNS_BASE_DIR",
    "RUNWAY_API_KEY",
    "RUNWAY_CAMERA_MOVEMENTS",
    "RUNWAY_MOVEMENT_TYPES",
    "RUNWAY_PROMPT_TEMPLATE",
    "SLEEP_SECONDS",
]

# Re-export modules from subpackages for backward compatibility
# Import specific classes and functions instead of using wildcard imports
# to avoid Final variable reassignment errors

# Content module imports
from youtube_shorts_gen.content.internet_content_fetcher import InternetContentFetcher
from youtube_shorts_gen.content.script_and_image_from_internet import (
    ScriptAndImageFromInternet,
)
from youtube_shorts_gen.content.script_and_image_gen import ScriptAndImageGenerator
from youtube_shorts_gen.content.story_prompt_gen import generate_dynamic_prompt

# Media module imports
from youtube_shorts_gen.media.paragraph_processor import ParagraphProcessor
from youtube_shorts_gen.media.paragraph_tts import ParagraphTTS
from youtube_shorts_gen.media.paragraph_tts_syncer import ParagraphTTSSyncer
from youtube_shorts_gen.media.runway import VideoGenerator
from youtube_shorts_gen.media.sync_video_with_tts import VideoAudioSyncer
from youtube_shorts_gen.media.tts_generator import TTSGenerator
from youtube_shorts_gen.media.video_audio_sync import (
    VideoAudioSyncer as NewVideoAudioSyncer,
)

# Upload module imports
from youtube_shorts_gen.upload.upload_history import UploadHistory
from youtube_shorts_gen.upload.upload_to_youtube import YouTubeUploader

# Utils module imports - import specific constants and functions
from youtube_shorts_gen.utils.config import (
    ACTIONS,
    ANIMALS,
    BACKGROUNDS,
    DANCES,
    EMPTY_IMAGE_B64,
    HUMANS,
    IMAGE_PROMPT_TEMPLATE,
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_QUALITY,
    OPENAI_IMAGE_SIZE,
    RUNS_BASE_DIR,
    RUNWAY_API_KEY,
    RUNWAY_CAMERA_MOVEMENTS,
    RUNWAY_MOVEMENT_TYPES,
    RUNWAY_PROMPT_TEMPLATE,
    SLEEP_SECONDS,
)
