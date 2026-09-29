"""Sign up, sign in, sign out."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.deps import COOKIE, current_user
from app.core.accounts import AccountError, User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str
    password: str


def _user_json(user: User) -> dict:
    return {"id": user.id, "username": user.username, "is_admin": user.is_admin}


def _start_session(request: Request, response: Response, user: User) -> None:
    settings = request.app.state.settings
    token = request.app.state.accounts.create_session(user.id)
    response.set_cookie(COOKIE, token, max_age=settings.session_days * 86400, httponly=True,
                        samesite="lax", secure=settings.cookie_secure, path="/")


@router.get("/status")
def status(request: Request) -> dict:
    """Public: lets the page decide between the app and the sign-in screen (and whether to offer
    'create account') in one request, without a 401 on first load."""
    accounts, settings = request.app.state.accounts, request.app.state.settings
    has_users = accounts.user_count() > 0
    user = accounts.user_for_token(request.cookies.get(COOKIE))
    return {"has_users": has_users, "registration_open": (not has_users) or settings.allow_registration,
            "user": _user_json(user) if user else None}


@router.post("/register", status_code=201)
def register(credentials: Credentials, request: Request, response: Response) -> dict:
    accounts, settings = request.app.state.accounts, request.app.state.settings
    if accounts.user_count() > 0 and not settings.allow_registration:
        raise HTTPException(status_code=403, detail="Registration is closed. Ask the owner to create your account "
                                                    "(they can turn on STUDYBOT_ALLOW_REGISTRATION).")
    try:
        user = accounts.create_user(credentials.username, credentials.password)
    except AccountError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _start_session(request, response, user)
    return _user_json(user)


@router.post("/login")
def login(credentials: Credentials, request: Request, response: Response) -> dict:
    accounts, limiter = request.app.state.accounts, request.app.state.limiter
    key = f"{request.client.host if request.client else '?'}|{credentials.username.strip().lower()}"
    wait = limiter.retry_after(key)
    if wait:
        raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {wait} seconds.",
                            headers={"Retry-After": str(wait)})
    user = accounts.authenticate(credentials.username, credentials.password)
    if user is None:
        limiter.record_failure(key)
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    limiter.reset(key)
    _start_session(request, response, user)
    return _user_json(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    request.app.state.accounts.end_session(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return _user_json(user)
