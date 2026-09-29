"""OKF API routes — browse, search and export knowledge nodes."""
from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import current_user
from app.core.accounts import User

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _node_json(node) -> dict:
    return {
        "id": node.node_id,
        "type": node.type,
        "title": node.title,
        "description": node.description,
        "body": node.body,
        "tags": node.tags,
        "trust": node.trust,
        "source_document": node.source_document,
        "document_id": node.document_id,
        "collection_id": node.collection_id,
    }


@router.get("")
def list_nodes(
    request: Request,
    collection_id: int | None = None,
    node_type: str | None = None,
    limit: int = 200,
    user: User = Depends(current_user),
) -> list[dict]:
    """List OKF knowledge nodes, optionally filtered by collection or type."""
    nodes = request.app.state.okf_store.list_nodes(
        collection_id=collection_id,
        user_id=user.id,
        node_type=node_type,
        limit=limit,
    )
    return [_node_json(n) for n in nodes]


@router.get("/search")
def search_nodes(
    request: Request,
    q: str,
    collection_id: int | None = None,
    k: int = 10,
    user: User = Depends(current_user),
) -> list[dict]:
    """Semantic search over OKF knowledge nodes."""
    embedder = request.app.state.bot.embedder
    query_vec = embedder.embed_query(q)
    results = request.app.state.okf_store.search(
        query_vector=query_vec,
        collection_id=collection_id,
        user_id=user.id,
        k=k,
    )
    return [{"score": round(r.score, 4), **_node_json(r.node)} for r in results]


@router.get("/stats")
def knowledge_stats(
    request: Request,
    collection_id: int | None = None,
    user: User = Depends(current_user),
) -> dict:
    """Return counts of knowledge nodes by type."""
    return request.app.state.okf_store.stats(
        collection_id=collection_id,
        user_id=user.id,
    )


@router.get("/{node_id}")
def get_node(
    node_id: int,
    request: Request,
    user: User = Depends(current_user),
) -> dict:
    """Get a single knowledge node by ID."""
    from fastapi import HTTPException
    node = request.app.state.okf_store.get_node(node_id, user.id)
    if node is None:
        raise HTTPException(status_code=404, detail="Knowledge node not found.")
    return _node_json(node)


@router.get("/export/zip")
def export_zip(
    request: Request,
    collection_id: int | None = None,
    user: User = Depends(current_user),
) -> StreamingResponse:
    """Export all OKF nodes as a ZIP of Markdown files."""
    nodes = request.app.state.okf_store.list_nodes(
        collection_id=collection_id,
        user_id=user.id,
        limit=10000,
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for node in nodes:
            tags_line = ", ".join(node.tags)
            content = (
                f"---\n"
                f"type: {node.type}\n"
                f"title: {node.title}\n"
                f"trust: {node.trust}\n"
                f"tags: [{tags_line}]\n"
                f"source: {node.source_document}\n"
                f"---\n\n"
                f"# {node.title}\n\n"
                f"**{node.description}**\n\n"
                f"{node.body}\n"
            )
            safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in node.title)[:60]
            filename = f"{node.type}/{safe_title}.md"
            zf.writestr(filename, content)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=knowledge.zip"},
    )
