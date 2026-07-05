from fastapi import APIRouter, Depends, Query

from app.deps import get_repository
from app.errors import NotFoundError
from app.models import LyricsResponse
from app.ratelimit import check_rate_limit
from app.repositories.base import SongRepository

router = APIRouter(tags=["lyrics"], dependencies=[Depends(check_rate_limit)])


@router.get("/songs/{song_id}/lyrics", response_model=LyricsResponse)
async def get_lyrics(
    song_id: int,
    time: float | None = Query(None),
    context: int = Query(1, ge=0, le=10),
    repo: SongRepository = Depends(get_repository),
):
    song = repo.get_song(song_id)
    if song is None:
        raise NotFoundError("Song", str(song_id))

    if time is not None:
        lyrics = repo.get_lyric_at_time(song_id, time, context)
        return LyricsResponse(
            song_id=song_id, lyrics=lyrics, time_sec=time, context=context
        )

    lyrics = repo.get_lyrics(song_id)
    return LyricsResponse(song_id=song_id, lyrics=lyrics)