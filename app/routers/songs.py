from fastapi import APIRouter, Depends, Query

from app.deps import get_repository
from app.errors import NotFoundError
from app.models import Song, SongsPage
from app.ratelimit import check_rate_limit
from app.repositories.base import SongRepository

router = APIRouter(tags=["songs"], dependencies=[Depends(check_rate_limit)])


@router.get("/songs", response_model=SongsPage)
async def list_songs(
    title: str | None = Query(None),
    artist: str | None = Query(None),
    writer: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    repo: SongRepository = Depends(get_repository),
):
    return repo.list_songs(
        title=title, artist=artist, writer=writer, page=page, size=size
    )


@router.get("/songs/{song_id}", response_model=Song)
async def get_song(
    song_id: int,
    repo: SongRepository = Depends(get_repository),
):
    song = repo.get_song(song_id)
    if song is None:
        raise NotFoundError("Song", str(song_id))
    return song