from app.models import Song, LyricLine, SongsPage


def test_get_song_existing(repo):
    song = repo.get_song(1)
    assert isinstance(song, Song)
    assert song.title == "测试A"
    assert song.artist == "艺术家1"
    assert song.lyricist == "作词人1"
    assert song.composer == "作曲人1"
    assert song.arranger == "编曲人1"
    assert song.has_translation is False
    assert song.version is None


def test_get_song_with_translation(repo):
    song = repo.get_song(2)
    assert song.has_translation is True
    assert song.version == "Live"


def test_get_song_not_found(repo):
    assert repo.get_song(999) is None


def test_list_songs_default(repo):
    page = repo.list_songs()
    assert isinstance(page, SongsPage)
    assert page.total == 3
    assert len(page.items) == 3
    assert page.page == 1
    assert page.size == 20


def test_list_songs_filter_title(repo):
    page = repo.list_songs(title="测试")
    assert page.total == 3


def test_list_songs_filter_artist(repo):
    page = repo.list_songs(artist="艺术家1")
    assert page.total == 2
    assert {s.id for s in page.items} == {1, 2}


def test_list_songs_filter_writer(repo):
    page = repo.list_songs(writer="作词人1")
    assert page.total == 2
    assert {s.id for s in page.items} == {1, 3}


def test_list_songs_pagination(repo):
    p1 = repo.list_songs(page=1, size=2)
    assert len(p1.items) == 2
    assert p1.total == 3
    assert p1.page == 1

    p2 = repo.list_songs(page=2, size=2)
    assert len(p2.items) == 1
    assert p2.total == 3
    assert p2.page == 2


def test_list_songs_no_match(repo):
    page = repo.list_songs(title="不存在")
    assert page.total == 0
    assert page.items == []


def test_list_songs_clamp_page(repo):
    p = repo.list_songs(page=0, size=1)
    assert p.page == 1


def test_list_songs_clamp_size(repo):
    p = repo.list_songs(page=1, size=0)
    assert p.size == 1


def test_search_all(repo):
    results = repo.search("暗里着迷")
    assert len(results) == 2
    assert {s.id for s in results} == {1, 3}


def test_search_by_title(repo):
    results = repo.search("测试A", scope=["title"])
    assert len(results) == 1
    assert results[0].id == 1


def test_search_by_lyrics(repo):
    results = repo.search("暗里着迷", scope=["lyrics"])
    assert len(results) == 2
    assert {s.id for s in results} == {1, 3}


def test_search_by_artist(repo):
    results = repo.search("艺术家1", scope=["artist"])
    assert len(results) == 2
    assert {s.id for s in results} == {1, 2}


def test_search_by_writer(repo):
    results = repo.search("作词人1", scope=["writer"])
    assert len(results) == 2
    assert {s.id for s in results} == {1, 3}


def test_search_empty_query(repo):
    assert repo.search("") == []
    assert repo.search("   ") == []


def test_search_no_match(repo):
    assert repo.search("不存在的内容") == []


def test_search_short_query(repo):
    results = repo.search("第三", scope=["lyrics"])
    assert len(results) == 1
    assert results[0].id == 1


def test_search_invalid_scope(repo):
    assert repo.search("测试A", scope=["nonexistent"]) == []


def test_get_lyrics(repo):
    lyrics = repo.get_lyrics(1)
    assert len(lyrics) == 3
    assert all(isinstance(ln, LyricLine) for ln in lyrics)
    assert lyrics[0].text == "第一行"
    assert lyrics[1].text == "暗里着迷"
    assert lyrics[1].translation == "secretly"
    assert lyrics[1].time_sec == 5.0


def test_get_lyrics_nonexisting(repo):
    assert repo.get_lyrics(999) == []


def test_get_lyric_at_time_exact(repo):
    result = repo.get_lyric_at_time(1, 5.0, context=1)
    assert len(result) == 3
    assert [ln.seq for ln in result] == [0, 1, 2]


def test_get_lyric_at_time_between(repo):
    result = repo.get_lyric_at_time(1, 7.5, context=1)
    assert len(result) == 3
    assert [ln.seq for ln in result] == [0, 1, 2]


def test_get_lyric_at_time_before_first(repo):
    result = repo.get_lyric_at_time(1, -1, context=1)
    assert len(result) == 3
    assert [ln.seq for ln in result] == [0, 1, 2]


def test_get_lyric_at_time_after_last(repo):
    result = repo.get_lyric_at_time(1, 999, context=1)
    assert [ln.seq for ln in result] == [1, 2]


def test_get_lyric_at_time_no_song(repo):
    assert repo.get_lyric_at_time(999, 0.0) == []


def test_get_lyric_at_time_first_line(repo):
    result = repo.get_lyric_at_time(1, 0.0, context=1)
    assert [ln.seq for ln in result] == [0, 1]