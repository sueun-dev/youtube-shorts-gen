from openai import OpenAI

from youtube_shorts_gen.utils.config import OPENAI_API_KEY

# Module-level client instance for reuse
_CLIENT = None


def get_openai_client() -> OpenAI:
    """Get an OpenAI client instance.
    
    Returns:
        An initialized OpenAI client instance.
        
    Raises:
        ValueError: If OPENAI_API_KEY environment variable is not set.
    """
    global _CLIENT
    
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in environment variables")
    
    if _CLIENT is None:
        _CLIENT = OpenAI(api_key=OPENAI_API_KEY)
        
    return _CLIENT
