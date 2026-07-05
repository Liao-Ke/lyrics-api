from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings, is_insecure
from app.errors import register_exception_handlers
from app.logging import logger
from app.middleware import register_middleware
from app.routers import health, lyrics, search, songs


def create_app() -> FastAPI:
    app = FastAPI(title="歌词API", version="1.0.0")

    register_exception_handlers(app)
    register_middleware(app)

    settings = get_settings()
    if settings.CORS_ORIGINS:
        origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET"],
            allow_headers=["Authorization"],
        )

    app.include_router(health.router)
    app.include_router(songs.router, prefix="/api/v1")
    app.include_router(lyrics.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")

    app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

    if is_insecure():
        logger.warning(
            "INSECURE: API_KEYS_ENABLED=false with non-localhost HOST={}",
            settings.HOST,
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)