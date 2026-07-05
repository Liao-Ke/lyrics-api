from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings, is_insecure
from app.errors import register_exception_handlers
from app.logging import logger, setup_logging
from app.middleware import register_middleware
from app.routers import health, lyrics, random, search, songs

setup_logging()


def create_app() -> FastAPI:
    app = FastAPI(title="歌词API", version="1.0.0")

    register_exception_handlers(app)
    register_middleware(app)

    app.include_router(health.router)
    app.include_router(songs.router, prefix="/api/v1")
    app.include_router(lyrics.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")
    app.include_router(random.router, prefix="/api/v1")

    if get_settings().METRICS_ENABLED:
        from fastapi.responses import Response
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        @app.get("/metrics", include_in_schema=False)
        async def get_metrics():
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

    if is_insecure():
        logger.warning(
            "INSECURE: API_KEYS_ENABLED=false with non-localhost HOST={}",
            get_settings().HOST,
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)