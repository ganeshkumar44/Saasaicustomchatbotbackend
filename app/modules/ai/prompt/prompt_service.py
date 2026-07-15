"""Prompt selection and merge logic for AI answer generation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.ai.prompt.default_prompt import DEFAULT_SYSTEM_PROMPT
from app.modules.prompt.model import ChatbotPrompt
from app.modules.prompt.utils import get_or_create_chatbot_prompt


def _has_custom_configuration(record: ChatbotPrompt) -> bool:
    return any(
        [
            record.system_prompt,
            record.tone,
            record.response_style,
            record.response_length,
            record.language,
            record.extra_instruction,
        ]
    )


def merge_prompt(record: ChatbotPrompt | None) -> str:
    """
    Merge the global default prompt with optional per-chatbot overrides.

    The default prompt is never fully replaced.
    """
    if record is None or not _has_custom_configuration(record):
        return DEFAULT_SYSTEM_PROMPT

    sections: list[str] = [DEFAULT_SYSTEM_PROMPT.strip(), ""]

    custom_sections: list[str] = []

    if record.system_prompt and record.system_prompt.strip():
        custom_sections.append(record.system_prompt.strip())

    if record.tone and record.tone.strip():
        custom_sections.append(f"Tone: {record.tone.strip()}")

    if record.response_style and record.response_style.strip():
        custom_sections.append(f"Response Style: {record.response_style.strip()}")

    if record.response_length and record.response_length.strip():
        custom_sections.append(f"Response Length: {record.response_length.strip()}")

    if record.language and record.language.strip():
        custom_sections.append(f"Language: {record.language.strip()}")

    if record.extra_instruction and record.extra_instruction.strip():
        custom_sections.append(f"Extra Instructions: {record.extra_instruction.strip()}")

    if custom_sections:
        sections.append("Additional Instructions:")
        sections.extend(custom_sections)

    return "\n".join(sections)


def get_chatbot_prompt_record(
    db: Session,
    chatbot_id: int,
) -> ChatbotPrompt:
    """Load the chatbot prompt row, creating a NULL-default row if missing."""
    return get_or_create_chatbot_prompt(db, chatbot_id)


def build_system_prompt(record: ChatbotPrompt | None) -> str:
    """Return the merged system prompt for AI generation."""
    return merge_prompt(record)


def get_system_prompt_for_chatbot(db: Session, chatbot_id: int) -> str:
    """Load chatbot prompt configuration and return the merged system prompt."""
    record = get_chatbot_prompt_record(db, chatbot_id)
    return build_system_prompt(record)
