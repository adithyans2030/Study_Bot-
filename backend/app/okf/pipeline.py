"""OKF Pipeline — called after ingest to extract and store knowledge nodes."""
from __future__ import annotations

import asyncio
import logging

from app.okf.generator import generate_nodes
from app.okf.store import OKFStore

log = logging.getLogger("studybot.okf.pipeline")


async def run_okf(
    okf_store: OKFStore,
    embedder,
    ollama_url: str,
    model: str,
    num_ctx: int,
    full_text: str,
    source_title: str,
    document_id: int,
    collection_id: int,
    user_id: int,
) -> int:
    """Extract OKF nodes from full_text and store them. Returns node count."""
    # Delete any previous nodes for this document (re-ingest case)
    okf_store.delete_by_document(document_id)

    # Generate nodes via LLM
    nodes = await generate_nodes(
        ollama_url=ollama_url,
        model=model,
        text=full_text,
        source_title=source_title,
        num_ctx=num_ctx,
    )
    if not nodes:
        log.warning("OKF: no nodes extracted for document %d ('%s')", document_id, source_title)
        return 0

    # Annotate nodes with metadata
    for node in nodes:
        node.document_id = document_id
        node.collection_id = collection_id
        node.user_id = user_id
        node.source_document = source_title

    # Embed node bodies for semantic search
    texts = [f"{n.title}\n{n.description}\n{n.body}" for n in nodes]
    embeddings = await asyncio.to_thread(embedder.embed_passages, texts)

    # Store in SQLite
    okf_store.insert_nodes(nodes, embeddings, document_id, collection_id, user_id)
    log.info("OKF: stored %d nodes for '%s' (doc %d)", len(nodes), source_title, document_id)
    return len(nodes)
