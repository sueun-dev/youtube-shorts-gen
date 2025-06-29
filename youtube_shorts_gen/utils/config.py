"""Configuration module for the YouTube Shorts generator.

This module contains all configuration parameters, constants, and templates used
throughout the YouTube Shorts generator application. It handles environment
variables, API keys, model configuration, and content generation templates.
"""

import os
from typing import Final

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
OPENAI_API_KEY: Final[str] = os.getenv("OPENAI_API_KEY", "")
RUNWAY_API_KEY: Final[str] = os.getenv("RUNWAY_API_KEY", "")

# Model Configuration
OPENAI_CHAT_MODEL: Final[str] = "gpt-4o-mini-2024-07-18"
OPENAI_IMAGE_MODEL: Final[str] = "gpt-image-1"

# Validate and set image size
_IMAGE_SIZES = {"1024x1024", "1792x1024", "1024x1792"}
_OPENAI_IMAGE_SIZE = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024")
if _OPENAI_IMAGE_SIZE not in _IMAGE_SIZES:
    error_msg = f"Invalid OPENAI_IMAGE_SIZE: {_OPENAI_IMAGE_SIZE}."
    error_msg += f" Must be one of {_IMAGE_SIZES}"
    raise ValueError(error_msg)
OPENAI_IMAGE_SIZE: Final[str] = _OPENAI_IMAGE_SIZE

# Validate and set image quality
_IMAGE_QUALITIES = {"medium", "high", "low"}
_OPENAI_IMAGE_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "medium").lower()
if _OPENAI_IMAGE_QUALITY not in _IMAGE_QUALITIES:
    error_msg = f"Invalid OPENAI_IMAGE_QUALITY: {_OPENAI_IMAGE_QUALITY}."
    error_msg += f" Must be one of {_IMAGE_QUALITIES}"
    raise ValueError(error_msg)
OPENAI_IMAGE_QUALITY: Final[str] = _OPENAI_IMAGE_QUALITY
# Content Elements for Story Generation
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

# Image Generation Prompt Template
IMAGE_PROMPT_TEMPLATE: Final[str] = (
    "Create an ultra-photorealistic, vertically framed cinematic scene inspired by "
    'the story: "{story}". '
    "Focus on a realistic everyday moment—objects resting naturally under gravity. "
    "Use soft, natural lighting (golden hour or diffused daylight) with gentle global illumination. "
    "Include realistic textures like glass, metal, fabric, and skin, without excessive micro‑detail. "
    "Choose a neutral camera angle (eye‑level or slight low‑angle), as if shot on a full‑frame DSLR (35mm f/1.8). "
    "Apply subtle depth of field for natural background blur. "
    "No surreal or levitating elements—everything grounded in real‑world physics. "
    "No text—tell the story purely through the visual."
)


# Runway Video Generation Prompt Template
RUNWAY_PROMPT_TEMPLATE: Final[str] = (
    "{camera_movement}: The scene features {subject} with realistic details and natural lighting. "
    "The subject {movement_type} with subtle and minimal motion. "
    "The environment is detailed with realistic textures and cinematic lighting."
)

# Runway Camera Movements
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

# Runway Movement Types
RUNWAY_MOVEMENT_TYPES: Final[list[str]] = [
    "grows",
    "emerges",
    "ascends",
    "transforms",
    "ripples",
    "unfolds",
]

# Fallback Image (1x1 transparent PNG in base64)
EMPTY_IMAGE_B64: Final[str] = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# Runtime Configuration
RUNS_BASE_DIR: Final[str] = "runs"
SLEEP_SECONDS: Final[int] = 120

# Runway Configuration
# Maximum number of Runway AI videos to generate per segment (to control API costs)
MAX_RUNWAY_VIDEOS_PER_SEGMENT: Final[int] = int(os.getenv("MAX_RUNWAY_VIDEOS_PER_SEGMENT", "4"))

# Chat Generation Defaults
CHAT_TEMPERATURE_DEFAULT: Final[float] = float(os.getenv("CHAT_TEMPERATURE", "0.9"))
CHAT_MAX_TOKENS_DEFAULT: Final[int] = int(os.getenv("CHAT_MAX_TOKENS", "300"))
