
import os

from dotenv import load_dotenv
from ollama import Client

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

client = Client(host=OLLAMA_HOST)


def generate_response(message: str) -> str:
    """Generate a response using the configured Ollama model.

    Args:
        message: Prompt sent to the model.

    Returns:
        Generated response text, or an empty string if absent.
    """
    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Nova, a helpful enterprise AI assistant. "
                    "Answer clearly and concisely. "
                    "Do not invent facts or database results."
                ),
            },
            {
                "role": "user",
                "content": message,
            },
        ],
    )
    return response.message.content or ""
