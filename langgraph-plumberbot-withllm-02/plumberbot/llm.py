import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic()  # reads ANTHROPIC_API_KEY from env
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
