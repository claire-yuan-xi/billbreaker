"""The FastAPI app. Run locally with: uvicorn billbreaker.main:app --reload --port 3000"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import pages
from .api import admin, bills, explain, news, status, watchlist
from .security import SecurityHeaders
from .templating import HERE, templates

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("billbreaker")


def create_app() -> FastAPI:
    app = FastAPI(title="Bill Breaker", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SecurityHeaders)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    for module in (pages, news, bills, explain, watchlist, admin, status):
        app.include_router(module.router)

    def wants_html(request: Request) -> bool:
        return not request.url.path.startswith("/api/")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and wants_html(request):
            return templates.TemplateResponse(request, "404.html", status_code=404)
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def bad_input(request: Request, exc: RequestValidationError):
        return JSONResponse({"error": "Invalid input"}, status_code=400)

    @app.exception_handler(Exception)
    async def crash(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        if wants_html(request):
            return templates.TemplateResponse(request, "error.html", status_code=500)
        return JSONResponse({"error": "Something went wrong"}, status_code=500)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(HERE / "static" / "favicon.ico")

    return app


app = create_app()
