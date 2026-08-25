from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.routes import router
from app.config import get_settings
from app.services.logging import configure_logging

configure_logging()
settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception):
    # Avoid leaking stack traces/secrets to clients. The server logger still captures the exception.
    import logging
    logging.getLogger("lenny.api").exception("unhandled_error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": {"code": "INTERNAL_ERROR", "message": "Unexpected server error."}})
