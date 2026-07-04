import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

llm = ChatAnthropic(model=_MODEL, temperature=0)
