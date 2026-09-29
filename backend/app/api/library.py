"""The user's library: collections (subjects) and the documents inside them."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from app.api.deps import clean_collection_name, current_user
from app.core.accounts import User
from app.core.uploads import UploadError, display_title, remove_upload, save_upload
from app.ingest.types import IngestError
from app.ingest.youtube_loader import is_youtube_url, parse_video_id
from app.rag.store import DocumentRecord

router = APIRouter(prefix="/api", tags=["library"])


class CollectionIn(BaseModel):
    name: str


class YouTubeIn(BaseModel):
    url: str
    collection: str | None = None


def document_json(doc: DocumentRecord) -> dict:
    """Public view of a document. Server file paths are never exposed; only YouTube URLs are."""
    return {"id": doc.id, "title": doc.title, "type": doc.source_type, "collection": doc.collection,
            "collection_id": doc.collection_id, "chunks": doc.chunk_count, "warnings": doc.warnings,
            "url": doc.source if doc.source_type == "youtube" else None, "added": doc.created_at}


# ---- collections -----------------------------------------------------------------------

@router.get("/collections")
def list_collections(request: Request, user: User = Depends(current_user)) -> list[dict]:
    rows = request.app.state.store.list_collections(user.id)
    return [{"id": r["id"], "name": r["name"], "documents": r["documents"], "chunks": r["chunks"]} for r in rows]


@router.post("/collections", status_code=201)
def create_collection(body: CollectionIn, request: Request, user: User = Depends(current_user)) -> dict:
    name = clean_collection_name(body.name, default="")
    collection_id = request.app.state.store.get_or_create_collection(name, user.id)
    return {"id": collection_id, "name": name}


@router.delete("/collections/{collection_id}", status_code=204)
def delete_collection(collection_id: int, request: Request, user: User = Depends(current_user)) -> Response:
    state = request.app.state
    sources = state.store.delete_collection(collection_id, user.id)
    if sources is None:
        raise HTTPException(status_code=404, detail="Collection not found.")
    for source in sources:
        remove_upload(source, state.settings.uploads_dir)
    return Response(status_code=204)


# ---- documents -------------------------------------------------------------------------

@router.get("/documents")
def list_documents(request: Request, collection: str | None = None, user: User = Depends(current_user)) -> list[dict]:
    store = request.app.state.store
    collection_id = None
    if collection:
        try:
            (collection_id,) = store.collection_ids([collection], user.id)
        except KeyError:
            return []
    return [document_json(d) for d in store.list_documents(collection_id, user.id)]


@router.get("/documents/{document_id}")
def get_document(document_id: int, request: Request, user: User = Depends(current_user)) -> dict:
    doc = request.app.state.store.get_document(document_id, user.id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document_json(doc)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, request: Request, user: User = Depends(current_user)) -> Response:
    state = request.app.state
    doc = state.store.get_document(document_id, user.id)
    if doc is None or not state.store.delete_document(document_id, user.id):
        raise HTTPException(status_code=404, detail="Document not found.")
    remove_upload(doc.source, state.settings.uploads_dir)
    return Response(status_code=204)


@router.post("/documents", status_code=202)
async def upload_document(request: Request, file: UploadFile = File(...), collection: str | None = Form(None),
                          user: User = Depends(current_user)) -> dict:
    """Accept a PDF/PPTX/DOCX, store it safely and queue it for indexing."""
    state = request.app.state
    limit = state.settings.max_upload_mb * 1024 * 1024
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit + 64 * 1024:
        raise HTTPException(status_code=413, detail=f"File is too large (limit {state.settings.max_upload_mb} MB).")
    name = clean_collection_name(collection)
    try:
        path, _kind = await save_upload(file, state.settings.uploads_dir / str(user.id), limit)
    except UploadError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    job = state.jobs.create(user.id, "file", str(path), name, title=display_title(file.filename))
    state.runner.notify()
    return job.public()


@router.post("/documents/youtube", status_code=202)
def add_youtube(body: YouTubeIn, request: Request, user: User = Depends(current_user)) -> dict:
    """Queue a YouTube video (its captions) for indexing. Only YouTube links are accepted."""
    state = request.app.state
    if not is_youtube_url(body.url):
        raise HTTPException(status_code=422, detail="Only YouTube links are supported.")
    try:
        video_id = parse_video_id(body.url)
    except IngestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = state.jobs.create(user.id, "youtube", f"https://www.youtube.com/watch?v={video_id}",
                            clean_collection_name(body.collection))
    state.runner.notify()
    return job.public()


@router.post("/documents/{document_id}/reindex", status_code=202)
def reindex_document(document_id: int, request: Request, user: User = Depends(current_user)) -> dict:
    state = request.app.state
    doc = state.store.get_document(document_id, user.id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    kind = "youtube" if doc.source_type == "youtube" else "reindex"
    job = state.jobs.create(user.id, kind, doc.source, doc.collection, title=doc.title, force=True)
    state.runner.notify()
    return job.public()
