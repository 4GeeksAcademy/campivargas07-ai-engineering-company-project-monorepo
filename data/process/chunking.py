"""Semantic, heading-aware chunking for the short Brasaland manuals."""

from __future__ import annotations

import re
from dataclasses import dataclass

from data.process.loader import SourceDocument

@dataclass(frozen=True)
class KnowledgeChunk:
    source_document: str
    section: str
    chunk_index: int
    text: str


def _paragraphs(markdown: str) -> list[tuple[str, str]]:
    """Return paragraphs paired with the closest literal Markdown heading."""
    current_heading: str | None = None
    result: list[tuple[str, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            text = "\n".join(line.rstrip() for line in buffer).strip()
            if text:
                result.append((current_heading or "", text))
            buffer.clear()

    for line in markdown.splitlines():
        if line.startswith("#") and re.match(r"^#{1,6}\s+", line):
            flush()
            current_heading = re.sub(r"^#{1,6}\s+", "", line).strip()
        elif not line.strip():
            flush()
        else:
            buffer.append(line)
    flush()
    return result


def chunk_document(document: SourceDocument) -> list[KnowledgeChunk]:
    """Group complete semantic paragraphs, retaining lists/conditions together."""
    paragraphs = _paragraphs(document.text)
    if not paragraphs:
        return []

    # Group adjoining paragraphs within each section. Lists stay atomic: their
    # conditions, exceptions and individual warnings must never be separated.
    grouped: list[tuple[str, list[str]]] = []
    for heading, paragraph in paragraphs:
        if grouped and grouped[-1][0] == heading:
            grouped[-1][1].append(paragraph)
        else:
            grouped.append((heading, [paragraph]))

    # Combine adjacent short sections into focused chunks. Headings are repeated
    # in the text so an extracted chunk remains understandable on its own.
    raw: list[tuple[str, str]] = []
    for heading, parts in grouped:
        body = "\n\n".join(parts)
        section = heading or document.title
        if raw and len(raw[-1][1]) < 650:
            old_heading, old_body = raw[-1]
            raw[-1] = (old_heading, f"{old_body}\n\n{section}\n{body}")
        else:
            raw.append((section, body))

    if len(raw) > 4:
        compact: list[tuple[str, str]] = []
        for index in range(0, len(raw), 2):
            heading, body = raw[index]
            if index + 1 < len(raw):
                next_heading, next_body = raw[index + 1]
                body = f"{body}\n\n{next_heading}\n{next_body}"
            compact.append((heading, body))
        raw = compact

    # These source manuals have several complete paragraphs in their opening
    # section. Split only at paragraph boundaries when fewer than three chunks
    # would otherwise result; never split a numbered or bulleted list.
    if len(raw) < 3:
        expanded: list[tuple[str, str]] = []
        for heading, body in raw:
            paragraphs_in_chunk = body.split("\n\n")
            if len(expanded) + len(paragraphs_in_chunk) + (len(raw) - 1) >= 3:
                expanded.extend((heading, part) for part in paragraphs_in_chunk)
            else:
                expanded.append((heading, body))
        if len(expanded) >= 3:
            raw = expanded

    return [
        KnowledgeChunk(
            source_document=document.source_document,
            section=heading,
            chunk_index=index,
            text=f"{document.title}\n{heading}\n\n{text}" if text else f"{document.title}\n{heading}",
        )
        for index, (heading, text) in enumerate(raw)
    ]


def chunk_documents(documents: list[SourceDocument]) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for document in documents:
        document_chunks = chunk_document(document)
        if len(document_chunks) < 3:
            raise ValueError(
                f"Expected at least three semantic chunks for {document.source_document}; "
                f"got {len(document_chunks)}"
            )
        chunks.extend(document_chunks)
    return chunks
