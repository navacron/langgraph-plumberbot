"""CLI entry point — connects to the LangGraph Server via HTTP.

Usage:
    python -m cli.main                        # run all three scenarios
    python -m cli.main --scenario missing
    python -m cli.main --scenario general
    python -m cli.main --scenario emergency

The server must be running before invoking the CLI:
    langgraph dev    # starts at http://127.0.0.1:2024 by default

LANGGRAPH_URL env var selects the server:
    http://127.0.0.1:2024              (default — langgraph dev)
    https://<id>.us.langgraph.app      (LangSmith Cloud after langgraph deploy)
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv
from langgraph_sdk import get_client

from .scenarios import run_general, run_missing, run_emergency

load_dotenv()


async def main(scenario: str) -> None:
    url = os.getenv("LANGGRAPH_URL", "http://127.0.0.1:2024")
    print(f"Connecting to LangGraph Server at: {url}\n")

    # Next.js equivalent: const client = new Client({ apiUrl: process.env.LANGGRAPH_URL })
    client = get_client(url=url)

    if scenario in ("general", "all"):
        await run_general(client)
    if scenario in ("missing", "all"):
        await run_missing(client)
    if scenario in ("emergency", "all"):
        await run_emergency(client)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Invoke the deployed PlumberBot via the LangGraph SDK"
    )
    parser.add_argument(
        "--scenario",
        default="all",
        choices=["general", "missing", "emergency", "all"],
        help="Which scenario to run (default: all)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.scenario))
