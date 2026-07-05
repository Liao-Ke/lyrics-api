from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.auth import KeyContext, verify_api_key_flexible
from app.deps import get_db_conn, get_repository
from app.errors import NotFoundError, ValidationError
from app.models import RandomLyricLine
from app.ratelimit import _enforce_rate_limit
from app.repositories.base import SongRepository

_VALID_FORMATS = frozenset({"json", "js"})

router = APIRouter(tags=["random"])


def _escape_js(s: str) -> str:
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace("</", "<\\/")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    return s


def _build_js(result: RandomLyricLine, target: str | None) -> str:
    text = _escape_js(result.text)
    title = _escape_js(result.song.title)
    artist = _escape_js(result.song.artist)
    translation = _escape_js(result.translation) if result.translation else None
    target_esc = _escape_js(target) if target else ""

    trans_json = "null" if translation is None else f"'{translation}'"

    return (
        f"(function(){{"
        f"var d={{text:'{text}',title:'{title}',artist:'{artist}',translation:{trans_json}}};"
        f"var sel='{target_esc}';"
        f"var el=sel?document.querySelector(sel):null;"
        f"if(!el){{el=document.createElement('div');document.body.appendChild(el);}}"
        f"el.className='lyric-random';"
        f"el.innerHTML='<p class=\"lyric-text\">\u300c'+d.text+'\u300d</p>'"
        f"+(d.translation?'<p class=\"lyric-tr\">'+d.translation+'</p>':'')"
        f"+'<p class=\"lyric-meta\">\u2014 '+d.title+' / '+d.artist+'</p>';"
        f"if(window.onRandomLyric)window.onRandomLyric(d);"
        f"}})()"
    )


@router.get("/random")
async def random_lyric(
    request: Request,
    response: Response,
    format: str = Query("json"),
    target: str | None = Query(None),
    min_chars: int = Query(1, ge=1, le=5000),
    max_chars: int = Query(200, ge=1, le=5000),
    artist: str | None = Query(None),
    writer: str | None = Query(None),
    version: str | None = Query(None),
    has_translation: bool | None = Query(None),
    repo: SongRepository = Depends(get_repository),
    key_ctx: KeyContext = Depends(verify_api_key_flexible),
    conn=Depends(get_db_conn),
):
    if format not in _VALID_FORMATS:
        e = ValidationError([{"field": "format", "message": "must be 'json' or 'js'"}])
        raise e

    _enforce_rate_limit(response, key_ctx, conn)

    result = repo.get_random_line(
        artist=artist,
        writer=writer,
        version=version,
        has_translation=has_translation,
        min_chars=min_chars,
        max_chars=max_chars,
    )

    if result is None:
        raise NotFoundError("Lyric", "random")

    if format == "js":
        js = _build_js(result, target)
        return PlainTextResponse(js, media_type="application/javascript")

    return result