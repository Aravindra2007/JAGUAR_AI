from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
WAKE_WORD = os.getenv("WAKE_WORD", "jaguar")

APP_NAME = "JAGUAR AI"
VERSION = "1.0.0"

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3"
)