"""
Knowledge chunks ORM models.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class KnowledgeChunk(Base):
    """Text chunk extracted from a knowledge base document for RAG processing."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chatbot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chatbots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledgebase_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chatbot = relationship("Chatbot", back_populates="knowledge_chunks")
    document = relationship("KnowledgebaseDocument", back_populates="chunks")

    def __repr__(self) -> str:
        return (
            f"<KnowledgeChunk id={self.id} document_id={self.document_id} "
            f"chunk_index={self.chunk_index}>"
        )
