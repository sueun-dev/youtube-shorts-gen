import random

from youtube_shorts_gen.utils.config import (
    ACTIONS,
    ANIMALS,
    BACKGROUNDS,
    DANCES,
    HUMANS,
)

_PROMPT_TEMPLATE = (
    "Write a cursed micro-story (max 3 sentences) set in {background}, "
    "where a {animal} and a {human} perform the {dance}. "
    "The story should feature surreal emotional twists and chaotic events—"
    "like when someone suddenly {action}. "
    "End with a haunting image. No logic, no numbers. Only vibes."
)


def generate_dynamic_prompt() -> str:
    """Generate a dynamic prompt by combining random elements.

    Returns:
        A complete prompt string for generating surreal micro-stories.
    """
    return _PROMPT_TEMPLATE.format(
        animal=random.choice(ANIMALS),
        human=random.choice(HUMANS),
        background=random.choice(BACKGROUNDS),
        dance=random.choice(DANCES),
        action=random.choice(ACTIONS),
    )
