"""Load only the four version-pinned Brasaland source manuals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CORPUS_REVISION = "48e21bb4c45a4101abb09cff8e6e0ad941c87847"
COMPANY = "brasaland"
LANGUAGE = "es"

@dataclass(frozen=True)
class SourceDocument:
    source_document: str
    title: str
    path: Path
    text: str


SOURCE_FILES: dict[str, tuple[str, str]] = {
    "loyalty-program": ("Programa de Lealtad \"Brasa Points\"", "brasaland-loyalty-program.es.md"),
    "waste-protocol": ("Protocolo de Control de Desperdicio", "brasaland-waste-protocol.es.md"),
    "menu-allergens": ("Guía de Alérgenos del Menú", "brasaland-menu-allergens.es.md"),
    "supplier-ordering": ("Procedimiento de Pedido a Proveedores", "brasaland-supplier-ordering.es.md"),
}


def corpus_directory() -> Path:
    """Resolve the repository corpus relative to this source file."""
    return Path(__file__).resolve().parents[2] / "docs" / "company-knowledge-base"


def load_documents(directory: Path | None = None) -> list[SourceDocument]:
    """Read the allow-listed Markdown files; never include incident context."""
    root = directory or corpus_directory()
    documents: list[SourceDocument] = []
    for slug, (title, filename) in SOURCE_FILES.items():
        path = root / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required knowledge source is missing: {filename}")
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(f"Knowledge source is empty: {filename}")
        documents.append(SourceDocument(slug, title, path, text))
    return documents
