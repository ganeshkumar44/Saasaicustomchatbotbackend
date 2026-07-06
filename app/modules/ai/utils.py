"""
AI answer generation helper utilities.
"""

from app.modules.ai.exceptions import (
    GeminiAPIError,
    GeminiAPIKeyMissingError,
    GeminiQuotaExceededError,
)
from app.modules.ai.providers.gemini_provider import GeminiProvider

NO_CONTEXT_ANSWER = "I don't have enough information in the knowledge base."

AI_PROMPT_TEMPLATE = """You are a helpful AI assistant.

Answer ONLY using the provided knowledge base context.

If the answer is not available in the provided context, respond exactly:

"I don't have enough information in the knowledge base."

Do not make up information.

Context:
{context}

Question:
{question}"""

_gemini_provider = GeminiProvider()


def normalize_question(question: str) -> str:
    """Normalize and validate a user question string."""
    return question.strip()


def build_ai_prompt(context: str, question: str) -> str:
    """Build the full prompt sent to an AI provider from context and question."""
    return AI_PROMPT_TEMPLATE.format(context=context, question=question)


def get_answer_from_gemini(prompt: str) -> str:
    """Backward-compatible wrapper around the Gemini provider."""
    return _gemini_provider.generate_answer(prompt)
