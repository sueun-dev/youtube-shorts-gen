"""Central configuration for the YouTube Shorts generator.

All tunable parameters, API keys, model identifiers, file names, and content
templates live here so the rest of the codebase never hard-codes magic values.
Environment variables (loaded from a local ``.env`` file) override the defaults
where it makes sense.
"""

import os
from typing import Final

from dotenv import load_dotenv

# Load environment variables from a local .env file, if present.
load_dotenv()


# --------------------------------------------------------------------------- #
# API keys
# --------------------------------------------------------------------------- #
OPENAI_API_KEY: Final[str] = os.getenv("OPENAI_API_KEY", "")
RUNWAY_API_KEY: Final[str] = os.getenv("RUNWAY_API_KEY", "")
ELEVENLABS_API_KEY: Final[str] = os.getenv("ELEVENLABS_API_KEY", "")


# --------------------------------------------------------------------------- #
# OpenAI model configuration
# --------------------------------------------------------------------------- #
OPENAI_CHAT_MODEL: Final[str] = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini-2024-07-18")
OPENAI_IMAGE_MODEL: Final[str] = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")


def _validate_choice(name: str, value: str, allowed: set[str]) -> str:
    """Return ``value`` if it is in ``allowed``; otherwise raise ``ValueError``."""
    if value not in allowed:
        raise ValueError(f"Invalid {name}: {value!r}. Must be one of {sorted(allowed)}")
    return value


# Sizes accepted by the gpt-image-1 model (square, landscape, portrait, auto).
IMAGE_SIZES: Final[set[str]] = {"1024x1024", "1536x1024", "1024x1536", "auto"}
OPENAI_IMAGE_SIZE: Final[str] = _validate_choice(
    "OPENAI_IMAGE_SIZE", os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"), IMAGE_SIZES
)

IMAGE_QUALITIES: Final[set[str]] = {"low", "medium", "high"}
OPENAI_IMAGE_QUALITY: Final[str] = _validate_choice(
    "OPENAI_IMAGE_QUALITY",
    os.getenv("OPENAI_IMAGE_QUALITY", "medium").lower(),
    IMAGE_QUALITIES,
)

# Chat generation defaults
CHAT_TEMPERATURE_DEFAULT: Final[float] = float(os.getenv("CHAT_TEMPERATURE", "0.9"))
CHAT_MAX_TOKENS_DEFAULT: Final[int] = int(os.getenv("CHAT_MAX_TOKENS", "300"))


# --------------------------------------------------------------------------- #
# ElevenLabs (text-to-speech) configuration
# --------------------------------------------------------------------------- #
ELEVENLABS_VOICE_ID: Final[str] = os.getenv(
    "ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"
)
ELEVENLABS_MODEL: Final[str] = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVENLABS_OUTPUT_FORMAT: Final[str] = os.getenv(
    "ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128"
)


# --------------------------------------------------------------------------- #
# Runway (image-to-video) configuration
# --------------------------------------------------------------------------- #
RUNWAY_MODEL: Final[str] = os.getenv("RUNWAY_MODEL", "gen3a_turbo")
RUNWAY_ASPECT_RATIO: Final[str] = os.getenv("RUNWAY_ASPECT_RATIO", "768:1280")
# Gen-3 Alpha Turbo supports clips up to 5 seconds.
RUNWAY_MAX_DURATION_SECONDS: Final[float] = 5.0
RUNWAY_DEFAULT_DURATION_SECONDS: Final[float] = 5.0
# How long to wait between task-status polls, and how many polls before giving up.
RUNWAY_POLL_INTERVAL_SECONDS: Final[int] = int(
    os.getenv("RUNWAY_POLL_INTERVAL_SECONDS", "20")
)
RUNWAY_MAX_POLL_ATTEMPTS: Final[int] = int(os.getenv("RUNWAY_MAX_POLL_ATTEMPTS", "30"))
# Maximum number of Runway AI videos to generate per segment (to control cost).
MAX_RUNWAY_VIDEOS_PER_SEGMENT: Final[int] = int(
    os.getenv("MAX_RUNWAY_VIDEOS_PER_SEGMENT", "4")
)


# --------------------------------------------------------------------------- #
# Video / FFmpeg encoding configuration
# --------------------------------------------------------------------------- #
# Vertical 9:16 Shorts resolution (width, height).
VIDEO_RESOLUTION: Final[tuple[int, int]] = (1080, 1920)
VIDEO_FPS: Final[int] = 30
FFMPEG_VIDEO_CODEC: Final[str] = "libx264"
FFMPEG_AUDIO_CODEC: Final[str] = "aac"
FFMPEG_AUDIO_BITRATE: Final[str] = "192k"
FFMPEG_CRF: Final[str] = "23"
FFMPEG_PRESET: Final[str] = "medium"
# Subprocess timeouts (seconds).
FFPROBE_TIMEOUT_SECONDS: Final[int] = 30
FFMPEG_SEGMENT_TIMEOUT_SECONDS: Final[int] = 60
FFMPEG_CONCAT_TIMEOUT_SECONDS: Final[int] = 120


# --------------------------------------------------------------------------- #
# Text-processing thresholds
# --------------------------------------------------------------------------- #
# Hard cap on how many paragraphs/segments a single Short is built from.
MAX_PARAGRAPHS_FOR_SHORTS: Final[int] = 8
# A paragraph longer than this many characters gets summarised before narration.
SUMMARIZE_THRESHOLD_CHARS: Final[int] = 300
# Transcript segmentation.
TRANSCRIPT_WORDS_PER_CHUNK: Final[int] = 500
TRANSCRIPT_MIN_TRAILING_CHUNK_WORDS: Final[int] = 100
TRANSCRIPT_MAX_CONTEXT_SUMMARIES: Final[int] = 2
TRANSCRIPT_MIN_LENGTH_CHARS: Final[int] = 30
# Internet-story sentence splitting.
MAX_STORY_SENTENCES: Final[int] = 8
MIN_SENTENCE_CHARS: Final[int] = 10


# --------------------------------------------------------------------------- #
# Shared output file names
# --------------------------------------------------------------------------- #
FINAL_VIDEO_FILENAME: Final[str] = "final_story_video.mp4"
STORY_PROMPT_FILENAME: Final[str] = "story_prompt.txt"
STORY_AUDIO_FILENAME: Final[str] = "story_audio.mp3"
OUTPUT_VIDEO_FILENAME: Final[str] = "output_story_video.mp4"


# --------------------------------------------------------------------------- #
# YouTube upload configuration
# --------------------------------------------------------------------------- #
# YouTube category 22 == "People & Blogs".
YOUTUBE_CATEGORY_ID: Final[str] = os.getenv("YOUTUBE_CATEGORY_ID", "22")
YOUTUBE_PRIVACY_STATUS: Final[str] = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
YOUTUBE_DEFAULT_TAGS: Final[list[str]] = [
    "AI short",
    "YouTube Shorts",
    "OpenAI",
    "RunwayML",
    "ElevenLabs",
]


# --------------------------------------------------------------------------- #
# Content elements for AI story generation
# --------------------------------------------------------------------------- #
ANIMALS: Final[list[str]] = [
    "Cat",
    "Squid",
    "Penguin",
    "Burning Water Deer",
    "Transparent Frog",
    "Disco Octopus",
    "Glow-in-the-dark Raccoon",
    "Breakdancing Koala",
    "Invisible Platypus",
    "Caffeinated Sloth",
]

HUMANS: Final[list[str]] = [
    "Awake but Lazy YouTuber",
    "Four-Eyed Grandma",
    "Frog with Milk Cap",
    "Ninja Grandpa on a Hoverboard",
    "Baby with Sunglasses and a Laptop",
    "Clown in Business Attire",
    "Chef Who Only Cooks Ice",
    "Boy Who Thinks He's a Drone",
    "Girl Covered in Stickers",
    "Time-Traveling Mime",
]

# https://www.youtube.com/watch?v=azF-fJCceMM
BACKGROUNDS: Final[list[str]] = [
    "Tralala World",
    "Bubblegum Subway",
    "Melting Playground",
    "Upside-Down Jungle",
    "Pixelated Sky Highway",
    "Underwater Arcade",
    "Rainbow Lava Lake",
    "Giant Sandwich Planet",
    "Cotton Candy Desert",
    "Ceiling of a Giant's Bedroom",
]

DANCES: Final[list[str]] = [
    "Tralala Ballet",
    "Bubblegum Tap",
    "Floating Kick",
    "Spinning Noodle Wiggle",
    "Penguin Moonwalk",
    "Crab Shuffle",
    "Electric Tofu Slide",
    "Space Cowboy Boogie",
    "Reverse Slow-Mo Wave",
    "Glitch-Hop Stomp",
]

ACTIONS: Final[list[str]] = [
    "Start crying",
    "Flip in the air",
    "Throw something",
    "Throw a chair",
    "Forget everything",
    "Scream into a donut",
    "Summon a mini tornado",
    "Hide inside a cereal box",
    "Explode into confetti",
    "Balance a piano on one toe",
]


# --------------------------------------------------------------------------- #
# Prompt templates
# --------------------------------------------------------------------------- #
IMAGE_PROMPT_TEMPLATE: Final[str] = (
    "Create an ultra-photorealistic, vertically framed cinematic scene inspired by "
    'the story: "{story}". '
    "Focus on a realistic everyday moment—objects resting naturally under gravity. "
    "Use soft, natural lighting (golden hour or diffused daylight) with gentle global "
    "illumination. "
    "Include realistic textures like glass, metal, fabric, and skin, without excessive "
    "micro-detail. "
    "Choose a neutral camera angle (eye-level or slight low-angle), as if shot on a "
    "full-frame DSLR (35mm f/1.8). "
    "Apply subtle depth of field for natural background blur. "
    "No surreal or levitating elements—everything grounded in real-world physics. "
    "No text—tell the story purely through the visual."
)

# Template for the per-line image prompt used by the YouTube-transcript pipeline
# (Korean political-news framing, matching the transcript segmenter prompts).
NEWS_SCENE_PROMPT_TEMPLATE: Final[str] = "정치 뉴스 장면: {text}"

# Runway video-generation prompt template.
RUNWAY_PROMPT_TEMPLATE: Final[str] = (
    "{camera_movement}: The scene features {subject} with realistic details and "
    "natural lighting. The subject {movement_type} with subtle and minimal motion. "
    "The environment is detailed with realistic textures and cinematic lighting."
)

RUNWAY_CAMERA_MOVEMENTS: Final[list[str]] = [
    "Low angle static shot",
    "High angle static shot",
    "Overhead shot",
    "FPV shot",
    "Hand held shot",
    "Wide angle shot",
    "Close up shot",
    "Macro cinematography",
    "Over the shoulder shot",
    "Tracking shot",
    "Establishing wide shot",
    "50mm lens shot",
    "Realistic documentary shot",
]

RUNWAY_MOVEMENT_TYPES: Final[list[str]] = [
    "grows",
    "emerges",
    "ascends",
    "transforms",
    "ripples",
    "unfolds",
]


# --------------------------------------------------------------------------- #
# Runtime configuration
# --------------------------------------------------------------------------- #
RUNS_BASE_DIR: Final[str] = "runs"
# How long main.py sleeps between successive pipeline runs.
SLEEP_SECONDS: Final[int] = int(os.getenv("SLEEP_SECONDS", "120"))
