"""
Structured content models used during knowledge base extraction.
"""

from dataclasses import dataclass, field


@dataclass
class ContentBlock:
    """A single structured unit extracted from a document."""

    block_type: str
    content: str
    order: int
    metadata: dict[str, str | int] = field(default_factory=dict)


@dataclass
class StructuredDocument:
    """Ordered collection of extracted content blocks."""

    blocks: list[ContentBlock] = field(default_factory=list)

    def add(
        self,
        block_type: str,
        content: str,
        *,
        metadata: dict[str, str | int] | None = None,
    ) -> None:
        """Append a non-empty content block."""
        normalized = content.strip()
        if not normalized:
            return
        self.blocks.append(
            ContentBlock(
                block_type=block_type,
                content=normalized,
                order=len(self.blocks),
                metadata=metadata or {},
            )
        )

    def merge_to_text(self) -> str:
        """Merge blocks in order into a single searchable document string."""
        parts: list[str] = []
        for block in sorted(self.blocks, key=lambda item: item.order):
            if block.block_type == "page_marker":
                parts.append(block.content)
                continue
            if block.block_type == "slide_marker":
                parts.append(block.content)
                continue
            if block.block_type == "heading":
                parts.append(f"# {block.content}")
                continue
            if block.block_type == "slide_title":
                parts.append(f"## {block.content}")
                continue
            if block.block_type == "table":
                parts.append(block.content)
                continue
            if block.block_type == "image_description":
                parts.append(f"[Image Description: {block.content}]")
                continue
            if block.block_type == "ocr_text":
                parts.append(f"[OCR Text]\n{block.content}")
                continue
            if block.block_type == "caption":
                parts.append(f"[Caption: {block.content}]")
                continue
            if block.block_type == "speaker_notes":
                parts.append(f"[Speaker Notes]\n{block.content}")
                continue
            parts.append(block.content)
        return "\n\n".join(parts)
