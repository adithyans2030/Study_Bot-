"""Small text helpers shared by the loaders."""
import hashlib
import re
from pathlib import Path

_PRIVATE_USE = re.compile("[-]")  # Word/Symbol-font bullets extract as these
_SPACES = re.compile(r"[ \t ]+")


def clean_text(text: str) -> str:
    text = _PRIVATE_USE.sub("", text).replace("​", "")
    text = _SPACES.sub(" ", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def prettify_stem(path: str | Path) -> str:
    """'Computer_Vision_Unit_1.pdf' -> 'Computer Vision Unit 1'."""
    return re.sub(r"[_\s]+", " ", Path(path).stem).strip()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_table(rows: list[list[str | None]]) -> str:
    """Render table rows so each row is self-describing, e.g.
    '- Method: Bilinear; Speed: Moderate'. Keeps comparisons retrievable after chunking."""
    cleaned = [[re.sub(r"\s+", " ", cell or "").strip() for cell in row] for row in rows]
    cleaned = [row for row in cleaned if any(row)]
    if not cleaned:
        return ""
    header, body = cleaned[0], cleaned[1:]
    if not body or len(header) < 2:
        return "\n".join(" | ".join(row) for row in cleaned)
    lines = ["Table columns: " + " | ".join(header)]
    for row in body:
        pairs = [f"{head}: {cell}" for head, cell in zip(header, row) if cell]
        if pairs:
            lines.append("- " + "; ".join(pairs))
    return "\n".join(lines)
