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
_IMAGE_QUALITIES = {"standard", "hd", "low"}
_OPENAI_IMAGE_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "low").lower()
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
    "The composition must be optimized for a 9:16 aspect ratio, centered for mobile "
    "Shorts viewing. "
    "Visualize a surreal dreamscape where gravity is defied—objects levitate, melt, "
    "and morph mid-air. "
    "Employ highly realistic lighting techniques, including global illumination, "
    "soft shadows, rim lighting, and bounce lighting. "
    "Incorporate ultra-detailed textures that mimic real-world materials such as "
    "glass, metal, skin (with pores), liquid, and fabric. "
    "Use an extreme and dramatic camera angle, such as a wide-angle lens or top-down "
    "drone perspective, to enhance cinematic depth. "
    "Apply vivid but natural color grading, similar to footage from a full-frame DSLR "
    "camera with a 35mm lens at f/1.4 during golden hour. "
    "Add cinematic depth of field, motion blur, and high-fidelity rendering of "
    "microscopic surface details (e.g., scratches, reflections, fibers). "
    "Exclude all textual elements; all narrative context must be conveyed visually "
    "through grounded yet surreal realism."
)

# Runway Video Generation Prompt Template
RUNWAY_PROMPT_TEMPLATE: Final[str] = (
    "Tracking shot: The camera moves through a surreal, dreamlike scene with "
    "{subject} in focus. "
    "The environment warps and undulates around the subject. "
    "Elements float and transform in slow motion with dramatic lighting. "
    "The colors shift and pulse with vibrant intensity."
)

# Runway Camera Movements
RUNWAY_CAMERA_MOVEMENTS: Final[list[str]] = [
    "Tracking shot",
    "Slow dolly zoom",
    "Low angle static shot",
    "Overhead pan",
    "Macro close-up",
    "Cinematic wide shot",
]

# Runway Movement Types
RUNWAY_MOVEMENT_TYPES: Final[list[str]] = [
    "warps and undulates",
    "floats and transforms",
    "shatters and reassembles",
    "melts and reforms",
    "pulses and vibrates",
    "spins and twists",
]

# Fallback Image (1x1 transparent PNG in base64)
EMPTY_IMAGE_B64: Final[str] = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# Runtime Configuration
RUNS_BASE_DIR: Final[str] = "runs"
SLEEP_SECONDS: Final[int] = 120
