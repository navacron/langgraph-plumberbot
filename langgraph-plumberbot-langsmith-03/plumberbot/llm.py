import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
llm = ChatAnthropic(model=MODEL, temperature=0)
