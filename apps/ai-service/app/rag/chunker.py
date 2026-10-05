"""Section-Aware Document Chunker for WanderAI RAG."""

import re
import hashlib
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class RAGChunk:
    chunk_id: str
    document_id: str
    title: str
    section_heading: str
    topic: str
    content: str
    content_hash: str
    source_name: str
    source_url: str
    license: str
    attribution: str
    language: str = "en"
    destination_id: Optional[str] = None
    place_id: Optional[str] = None
    category: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retrieved_at: Optional[Any] = None  # datetime of upstream retrieval; None -> database NOW()


class SectionAwareChunker:
    """Parses structured documents with headings into clean, section-aware chunks."""

    TOPIC_MAPPINGS = {
        "eat": "culinary",
        "drink": "culinary",
        "food": "culinary",
        "cuisine": "culinary",
        "climate": "climate",
        "weather": "climate",
        "when to go": "climate",
        "get in": "transport",
        "get around": "transport",
        "by plane": "transport",
        "by train": "transport",
        "by bus": "transport",
        "by car": "transport",
        "by boat": "transport",
        "history": "history",
        "background": "history",
        "culture": "culture",
        "etiquette": "culture",
        "respect": "culture",
        "see": "attractions",
        "do": "activities",
        "buy": "shopping",
        "sleep": "accommodation",
        "stay safe": "safety",
        "stay healthy": "health",
        "connect": "communications",
    }

    def __init__(self, target_chunk_words: int = 250, max_chunk_words: int = 450, overlap_sentences: int = 1):
        self.target_chunk_words = target_chunk_words
        self.max_chunk_words = max_chunk_words
        self.overlap_sentences = overlap_sentences

    @staticmethod
    def compute_hash(text: str) -> str:
        """Compute deterministic SHA-256 hash of normalized text."""
        normalized = " ".join(text.strip().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def infer_topic(self, heading: str) -> str:
        """Infer semantic topic from section heading."""
        cleaned = heading.lower().strip()
        for key, topic in self.TOPIC_MAPPINGS.items():
            if key in cleaned:
                return topic
        return "general"

    def split_into_sections(self, text: str) -> List[Dict[str, str]]:
        """Split text by markdown/wikitext headings (== Heading == or ### Heading)."""
        # Match lines like "== Heading ==" or "=== Subheading ===" or "## Heading"
        heading_pattern = re.compile(r"^(?:={2,4}\s*(.*?)\s*={2,4}|#{1,4}\s*(.*?))$", re.MULTILINE)
        
        sections = []
        matches = list(heading_pattern.finditer(text))
        
        if not matches:
            return [{"heading": "Introduction", "body": text.strip()}]
        
        # Check text before first heading
        first_start = matches[0].start()
        if first_start > 0:
            intro_body = text[:first_start].strip()
            if intro_body:
                sections.append({"heading": "Introduction", "body": intro_body})
        
        for i, match in enumerate(matches):
            raw_heading = match.group(1) or match.group(2) or "Section"
            heading = raw_heading.strip()
            
            start_body = match.end()
            end_body = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start_body:end_body].strip()
            
            if body:
                sections.append({"heading": heading, "body": body})
        
        return sections

    def _split_body_into_chunks(self, body: str) -> List[str]:
        """Split section body into word-bounded chunks preserving sentence structure."""
        sentences = re.split(r"(?<=[.!?])\s+", body)
        if not sentences:
            return []

        chunks = []
        current_sentences = []
        current_word_count = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            words = len(sentence.split())
            
            if current_word_count + words > self.max_chunk_words and current_sentences:
                chunks.append(" ".join(current_sentences))
                # Keep overlap sentences
                current_sentences = current_sentences[-self.overlap_sentences:] if self.overlap_sentences > 0 else []
                current_word_count = sum(len(s.split()) for s in current_sentences)

            current_sentences.append(sentence)
            current_word_count += words

        if current_sentences:
            chunks.append(" ".join(current_sentences))

        return chunks

    def chunk_document(
        self,
        document_id: str,
        title: str,
        text: str,
        source_name: str,
        source_url: str,
        license: str,
        attribution: str,
        language: str = "en",
        destination_id: Optional[str] = None,
        place_id: Optional[str] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[RAGChunk]:
        """Chunk a document preserving section headings, metadata, and topic tags."""
        sections = self.split_into_sections(text)
        chunks: List[RAGChunk] = []
        doc_meta = metadata or {}

        for sec_idx, section in enumerate(sections):
            heading = section["heading"]
            body = section["body"]
            topic = self.infer_topic(heading)
            
            body_chunks = self._split_body_into_chunks(body)
            for part_idx, body_chunk in enumerate(body_chunks):
                if len(body_chunk.split()) < 10:  # Skip trivial fragments
                    continue

                # Contextual chunk header
                contextual_content = f"{title} - {heading}\n{body_chunk}"
                c_hash = self.compute_hash(contextual_content)
                chunk_id = f"{document_id}-s{sec_idx}-p{part_idx}"

                chunk = RAGChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    title=title,
                    section_heading=heading,
                    topic=topic,
                    content=contextual_content,
                    content_hash=c_hash,
                    source_name=source_name,
                    source_url=source_url,
                    license=license,
                    attribution=attribution,
                    language=language,
                    destination_id=destination_id,
                    place_id=place_id,
                    category=category or topic,
                    metadata={
                        **doc_meta,
                        "section_index": sec_idx,
                        "part_index": part_idx,
                        "word_count": len(body_chunk.split()),
                    },
                )
                chunks.append(chunk)

        return chunks
