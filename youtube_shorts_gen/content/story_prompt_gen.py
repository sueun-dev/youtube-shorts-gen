import random

from youtube_shorts_gen.utils.config import (
    ACTIONS,
    ANIMALS,
    BACKGROUNDS,
    DANCES,
    HUMANS,
)


def generate_dynamic_prompt() -> str:
    """Generate a dynamic prompt by combining random elements.

    Returns:
        A complete prompt string for generating surreal micro-stories.
    """
    animal = random.choice(ANIMALS)
    human = random.choice(HUMANS)
    background = random.choice(BACKGROUNDS)
    dance = random.choice(DANCES)
    action = random.choice(ACTIONS)

    return (
        f"Write a cursed micro-story (max 3 sentences) set in {background}, "
        f"where a {animal} and a {human} perform the {dance}. "
        f"The story should feature surreal emotional twists and chaotic events—"
        f"like when someone suddenly {action}. "
        f"End with a haunting image. No logic, no numbers. Only vibes."
    )
