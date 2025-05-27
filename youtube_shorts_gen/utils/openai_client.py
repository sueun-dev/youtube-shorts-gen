"""OpenAI client utility module.

This module provides a centralized OpenAI client instance that can be used
throughout the codebase to avoid creating multiple client instances.
"""

from openai import OpenAI

from youtube_shorts_gen.utils.config import OPENAI_API_KEY


class OpenAIClientSingleton:
    """Singleton class for OpenAI client."""

    _instance: OpenAI | None = None

    @classmethod
    def get_client(cls) -> OpenAI:
        """Get the OpenAI client instance.

        Returns:
            OpenAI client instance

        Raises:
            ValueError: If OPENAI_API_KEY is not set
        """
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in environment variables")

        if cls._instance is None:
            cls._instance = OpenAI(api_key=OPENAI_API_KEY)

        return cls._instance


# Convenience function to get the OpenAI client
def get_openai_client() -> OpenAI:
    """Get the OpenAI client instance.

    Returns:
        OpenAI client instance
    """
    return OpenAIClientSingleton.get_client()
