"""Model configuration and initialization."""

import os
from langchain.chat_models import init_chat_model


def get_model():
    """Initialize and return the chat model.
    
    Returns:
        The initialized chat model
    """
    return init_chat_model(
        "openai:gpt-4o",
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url="http://api.pinkyne.com/v1/",
    )

