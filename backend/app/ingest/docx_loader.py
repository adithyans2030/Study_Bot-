"""Word loader (python-docx). Heading styles define structure; tables become self-describing rows."""
import re
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ingest.text_utils import clean_text, prettify_stem, render_table, sha256_file
from app.ingest.types import IngestError, LoadedDocument, Segment

_HEADING = re.compile(r"^Heading (\d)$")


def load_docx(path: str | Path) -> LoadedDocument:
    path = Path(path)
    try:
        document = Document(path)
    except Exception as exc:
        raise IngestError(f"Could not open Word document '{path.name}'. The file may be damaged.") from exc

    segments: list[Segment] = []
    heading_path: list[str] = []

    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, document)
            text = clean_text(paragraph.text)
            if not text:
                continue
            style = paragraph.style.name if paragraph.style is not None else ""
            match = _HEADING.match(style or "")
            if match:
                level = int(match.group(1))
                del heading_path[level - 1:]
                heading_path.append(text)
            elif style == "Title":
                continue
            else:
                if "List" in (style or ""):
                    text = "- " + text
                segments.append(Segment(text=text, heading=tuple(heading_path)))
        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            table_text = render_table([[cell.text for cell in row.cells] for row in table.rows])
            if table_text:
                segments.append(Segment(text=table_text, heading=tuple(heading_path)))

    if not segments:
        raise IngestError(f"No text found in '{path.name}'.")

    return LoadedDocument(
        title=prettify_stem(path),
        source_type="docx",
        source=str(path.resolve()),
        content_hash=sha256_file(path),
        segments=segments,
    )
