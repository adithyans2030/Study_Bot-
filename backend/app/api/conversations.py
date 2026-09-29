"""Saved chats: list, reopen, delete. (New chats are created by the first question sent to /api/chat.)"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import current_user
from app.core.accounts import User

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
def list_conversations(request: Request, user: User = Depends(current_user)) -> list[dict]:
    return [c.public() for c in request.app.state.conversations.list_for_user(user.id)]


@router.get("/{conversation_id}")
def get_conversation(conversation_id: int, request: Request, user: User = Depends(current_user)) -> dict:
    chats = request.app.state.conversations
    conversation = chats.get(conversation_id, user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {**conversation.public(), "messages": [m.public() for m in chats.messages(conversation_id, user.id)]}


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, request: Request, user: User = Depends(current_user)) -> Response:
    if not request.app.state.conversations.delete(conversation_id, user.id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return Response(status_code=204)
