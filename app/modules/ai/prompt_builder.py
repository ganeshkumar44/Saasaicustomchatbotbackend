"""Backward-compatible re-exports for the refactored prompt module."""

from app.modules.ai.prompt.default_prompt import DEFAULT_SYSTEM_PROMPT, NO_CONTEXT_ANSWER
from app.modules.ai.prompt.prompt_builder import build_final_prompt as build_ai_prompt

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "NO_CONTEXT_ANSWER",
    "SYSTEM_INSTRUCTIONS",
    "build_ai_prompt",
]

# Legacy alias used by older imports.
SYSTEM_INSTRUCTIONS = DEFAULT_SYSTEM_PROMPT
