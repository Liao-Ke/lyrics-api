from fastapi import APIRouter, Depends, Query

from app.deps import get_repository
from app.models import SearchResponse
from app.ratelimit import check_rate_limit
from app.repositories.base import SongRepository

_VALID_SCOPES = frozenset({"title", "artist", "writer", "lyrics"})

router = APIRouter(tags=["search"], dependencies=[Depends(check_rate_limit)])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    scope: str | None = Query(None),
    repo: SongRepository = Depends(get_repository),
):
    scope_list: list[str] | None = None
    if scope:
        parts = [s.strip() for s in scope.split(",") if s.strip()]
        scope_list = [s for s in parts if s in _VALID_SCOPES] or None

    results = repo.search(q, scope_list)
    active_scope = scope_list or ["title", "artist", "writer", "lyrics"]
    return SearchResponse(query=q, scope=active_scope, total=len(results), items=results)