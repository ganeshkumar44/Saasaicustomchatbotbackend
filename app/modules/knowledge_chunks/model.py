"""
Knowledge chunks ORM models.

The KnowledgeChunk model is defined in the knowledge base module and re-exported here
for backward compatibility with the knowledge_chunks package.
"""

from app.modules.knowledgebase.model import KnowledgeChunk

__all__ = ["KnowledgeChunk"]
