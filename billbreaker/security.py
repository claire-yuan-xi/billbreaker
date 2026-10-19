"""Standard security headers on every response; a CSP on HTML pages."""

from starlette.middleware.base import BaseHTTPMiddleware

CSP = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'", "'wasm-unsafe-eval'", "https://cdn.jsdelivr.net"],
    "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    "font-src": ["'self'", "https://fonts.gstatic.com", "data:"],
    "img-src": ["'self'", "data:", "https:"],
    "connect-src": ["'self'", "https://cdn.jsdelivr.net", "https://huggingface.co", "https://*.hf.co"],
    "worker-src": ["'self'", "blob:"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'self'"],
}

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    "X-DNS-Prefetch-Control": "off",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def build_csp() -> str:
    return "; ".join(f"{k} {' '.join(v)}" for k, v in CSP.items())


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for k, v in HEADERS.items():
            response.headers.setdefault(k, v)
        if "text/html" in response.headers.get("content-type", ""):
            response.headers.setdefault("Content-Security-Policy", build_csp())
        return response
