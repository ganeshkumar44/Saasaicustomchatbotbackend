"""Build the final prompt string sent to AI providers."""

from __future__ import annotations


def build_final_prompt(
    *,
    system_prompt: str,
    knowledge_context: str,
    question: str,
    conversation_history: str | None = None,
) -> str:
    """
    Assemble the complete prompt from prepared sections.

    This module does not load prompts from the database or apply merge logic.
    """
    sections = [system_prompt.strip(), ""]

    if conversation_history and conversation_history.strip():
        sections.extend(
            [
                "Recent Conversation:",
                conversation_history.strip(),
                "",
            ]
        )

    sections.extend(
        [
            "Knowledge Base Context:",
            knowledge_context.strip(),
            "",
            "User Question:",
            question.strip(),
            "",
            "Answer:",
        ]
    )
    return "\n".join(sections)
