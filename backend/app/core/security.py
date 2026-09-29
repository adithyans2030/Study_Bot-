"""Security middleware: cross-site request blocking and browser hardening headers."""
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import Settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# style-src allows inline styles: Radix Primitives (Tooltip/Popover/Select/DropdownMenu, used
# throughout the React frontend) position themselves with JS-computed inline `style="..."`
# attributes, which a strict style-src silently strips rather than just warning about — confirmed
# against the real built app (see tests/test_pwa.py). CSP has no nonce/hash mechanism for inline
# attributes with dynamic, per-render values (only for <style> elements), so 'unsafe-inline' is
# the only way to keep them working. It's narrowed with the CSP3 style-src-elem/style-src-attr
# split: style-src-elem stays strict (no relaxation needed — nothing here uses inline <style>
# blocks or dangerouslySetInnerHTML), so only the specific `style` attribute is relaxed, not
# arbitrary injected stylesheets. Browsers without CSP3 support fall back to the plain style-src
# above, which is why it keeps 'unsafe-inline' too. script-src is the one that actually matters
# for XSS and stays at 'self' with no relaxation, in either directive.
CSP = ("default-src 'self'; img-src 'self' data:; "
       "style-src 'self' 'unsafe-inline'; style-src-elem 'self'; style-src-attr 'unsafe-inline'; "
       "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
DOC_PATHS = ("/docs", "/redoc", "/openapi.json")  # Swagger UI needs inline scripts, so no CSP there


def allowed_hosts(settings: Settings) -> set[str]:
    return {urlparse(o.strip()).netloc for o in settings.allowed_origins.split(",") if o.strip()}


def install(app: FastAPI, settings: Settings) -> None:
    extra_hosts = allowed_hosts(settings)

    @app.middleware("http")
    async def harden(request: Request, call_next):
        if request.method in UNSAFE_METHODS:
            # Cookies are SameSite=Lax already; this also rejects a forged cross-site POST from
            # older browsers. Requests without an Origin header (curl, scripts) are not browsers
            # acting on a victim's behalf, and still need a valid session cookie.
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc not in ({request.headers.get("host", "")} | extra_hosts):
                return JSONResponse({"detail": "Cross-site request blocked."}, status_code=403)
        response = await call_next(request)
        for name, value in HEADERS.items():
            if name == "Content-Security-Policy" and request.url.path.startswith(DOC_PATHS):
                continue
            response.headers.setdefault(name, value)
        return response
