# config.py

import os

from dotenv import load_dotenv

from youtube_shorts_gen.story_prompt_gen import generate_dynamic_prompt

# === Load .env variables ===
load_dotenv()

# === API Keys ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")

# === Model Configuration ===
OPENAI_CHAT_MODEL = "gpt-4o-mini-2024-07-18"
OPENAI_IMAGE_MODEL = "gpt-image-1"
OPENAI_IMAGE_SIZE = "1024x1024"

# === Prompts ===
def get_story_prompt():
    return generate_dynamic_prompt()

IMAGE_PROMPT_TEMPLATE = (
    'Create a chaotic, visually intense dreamscape inspired by the story: "{story}". '
    'The scene should burst with kinetic energy—depict unhinged motion, '
    'clashing colors, and surreal transformations. '
    'Imagine gravity is broken: objects levitate, melt, or morph mid-air. '
    'Use cinematic lighting, extreme perspectives, '
    'and exaggerated contrasts to heighten emotion and tension. '
    'No text should be present; express the narrative through pure, wild symbolism.'
)

# === Fallback Image (1x1 PNG) ===
EMPTY_IMAGE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# === Runtime Configuration ===
RUNS_BASE_DIR = "runs"
SLEEP_SECONDS = 120
