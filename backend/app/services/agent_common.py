"""Shared helpers for Claude Agent SDK calls (used by enrichment + threat agents)."""

from __future__ import annotations

import json
import re
from typing import Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)


async def run_query(prompt: str, options: ClaudeAgentOptions) -> str:
    """Run one agent turn and return the final text (ResultMessage.result, else joined text)."""
    chunks: list[str] = []
    result_text: Optional[str] = None
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)
        elif isinstance(msg, ResultMessage):
            result_text = getattr(msg, "result", None)
    return (result_text or "\n".join(chunks)).strip()


def extract_json(text: str) -> dict:
    """Pull a single JSON object out of a possibly fenced/prosey model response."""
    t = text.strip()
    if "```" in t:
        t = re.sub(r"```(json)?", "", t).strip()
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j != -1:
        t = t[i : j + 1]
    return json.loads(t)
