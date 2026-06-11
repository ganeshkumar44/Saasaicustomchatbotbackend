import unittest

from app.modules.knowledgebase.service import generate_chunks_from_text
from app.modules.knowledgebase.utils import split_text_into_chunks


class KnowledgebaseChunkingTests(unittest.TestCase):
    def test_empty_text_returns_empty_list(self) -> None:
        self.assertEqual(split_text_into_chunks(""), [])
        self.assertEqual(split_text_into_chunks("   "), [])

    def test_2500_character_text_produces_three_chunks(self) -> None:
        text = "a" * 2500
        chunks = split_text_into_chunks(text, chunk_size=1000, overlap=200)

        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0]["chunk_index"], 1)
        self.assertEqual(chunks[1]["chunk_index"], 2)
        self.assertEqual(chunks[2]["chunk_index"], 3)

        self.assertEqual(chunks[0]["chunk_text"], "a" * 1000)
        self.assertEqual(chunks[1]["chunk_text"], "a" * 1000)
        self.assertEqual(chunks[2]["chunk_text"], "a" * 900)

        self.assertEqual(chunks[0]["character_count"], 1000)
        self.assertEqual(chunks[1]["character_count"], 1000)
        self.assertEqual(chunks[2]["character_count"], 900)

    def test_overlap_is_applied_correctly(self) -> None:
        text = "abcdefghijklmnopqrstuvwxyz" * 50
        chunks = split_text_into_chunks(text, chunk_size=1000, overlap=200)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[1]["chunk_text"][:200], chunks[0]["chunk_text"][-200:])

    def test_no_content_loss(self) -> None:
        text = "The quick brown fox jumps over the lazy dog. " * 80
        chunks = split_text_into_chunks(text.strip(), chunk_size=1000, overlap=200)
        reconstructed = chunks[0]["chunk_text"]

        for chunk in chunks[1:]:
            overlap_text = chunk["chunk_text"][:200]
            self.assertTrue(reconstructed.endswith(overlap_text))
            reconstructed += chunk["chunk_text"][200:]

        self.assertEqual(reconstructed, text.strip())

    def test_generate_chunks_from_text_uses_service_wrapper(self) -> None:
        text = "x" * 2500
        chunks = generate_chunks_from_text(text)

        self.assertEqual(len(chunks), 3)
        self.assertIn("chunk_index", chunks[0])
        self.assertIn("chunk_text", chunks[0])
        self.assertIn("character_count", chunks[0])


if __name__ == "__main__":
    unittest.main()
