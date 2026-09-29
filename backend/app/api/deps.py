"""Shared request helpers: who is signed in, and input validation."""
import re

from fastapi import HTTPException, Request

from app.core.accounts import User

COOKIE = "studybot_session"
_COLLECTION = re.compile(r"^\w[\w .&'()-]{0,59}$")


def current_user(request: Request) -> User:
    user = request.app.state.accounts.user_for_token(request.cookies.get(COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in.")
    return user


def clean_collection_name(name: str | None, default: str = "General") -> str:
    name = (name or default).strip()
    if not _COLLECTION.match(name):
        raise HTTPException(status_code=422, detail="Collection names use letters, numbers, spaces and - _ . & ' ( ) "
                                                    "(1-60 characters).")
    return name
