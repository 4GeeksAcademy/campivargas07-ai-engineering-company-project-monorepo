"""Semantic blocks tailored to the four official manuals; original bytes stay intact."""
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid5

from data.process.config import ROOT, OWNER

SLUGS = ("loyalty-program", "waste-protocol", "menu-allergens", "supplier-ordering")
SECTIONS = {
    "loyalty-program": ("Acumulación y vigencia", "Niveles", "Redención", "Transferencia a la app", "Preguntas frecuentes"),
    "waste-protocol": ("Registro, procedimiento y excepciones", "Escalamiento", "Meta operativa"),
    "menu-allergens": ("Platos y advertencias", "Protocolo de alergias", "Costilla BBQ y certificación"),
    "supplier-ordering": ("Responsable y horario", "Frecuencias y entregas", "Stock mínimo y emergencias"),
}


def load_chunks(directory: Path = ROOT / "docs/company-knowledge-base") -> list[dict]:
    chunks = []
    for slug in SLUGS:
        text = (directory / f"brasaland-{slug}.es.md").read_text(encoding="utf-8").strip()
        blocks = re.split(r"\n\s*\n", text)
        title, body = blocks[0], blocks[1:]
        # Fail closed on structural changes rather than silently splitting a rule.
        expected = {"loyalty-program": 5, "waste-protocol": 5, "menu-allergens": 4, "supplier-ordering": 4}
        if not title.startswith("# ") or len(body) != expected[slug]:
            raise ValueError(f"Revisar estructura semántica del manual {slug}")
        if slug == "waste-protocol":
            groups = [body[:3], body[3:4], body[4:]]
        elif slug == "supplier-ordering":
            groups = [body[:1], body[1:2], body[2:]]
        elif slug == "menu-allergens":
            # Every allergen answer carries the complete safety protocol and BBQ exception.
            groups = [body, [body[0], body[2], body[3]], [body[3], body[2]]]
        else:
            groups = [[b] for b in body]
        for index, (section, group) in enumerate(zip(SECTIONS[slug], groups, strict=True)):
            content = title + "\n\n" + "\n\n".join(group)
            chunks.append({"id": str(uuid5(NAMESPACE_URL, f"{OWNER}/{slug}/{index}")),
                           "payload": {"company": "brasaland", "source_document": slug,
                                       "section": section, "language": "es", "chunk_index": index,
                                       "text": content, "managed_by": OWNER}})
    return chunks
