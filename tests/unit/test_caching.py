import time

from app.repositories.caching import CachingSongRepository


class TestCaching:
    def test_hit_returns_cached(self, repo):
        cached = CachingSongRepository(repo)
        first = cached.get_song(1)
        second = cached.get_song(1)
        assert second is first

    def test_miss_different_keys(self, repo):
        cached = CachingSongRepository(repo)
        s1 = cached.get_song(1)
        s2 = cached.get_song(2)
        assert s1 is not s2

    def test_miss_different_methods(self, repo):
        cached = CachingSongRepository(repo)
        song = cached.get_song(1)
        lyrics = cached.get_lyrics(1)
        assert lyrics is not song

    def test_ttl_expiry(self, repo):
        cached = CachingSongRepository(repo, ttl_sec=0)
        time.sleep(0.001)
        first = cached.get_song(1)
        second = cached.get_song(1)
        assert second is not first

    def test_list_songs_bypasses_cache(self, repo):
        cached = CachingSongRepository(repo)
        page1 = cached.list_songs(page=1, size=20)
        page2 = cached.list_songs(page=1, size=20)
        assert page2 is not page1

    def test_search_caches(self, repo):
        cached = CachingSongRepository(repo)
        r1 = cached.search("暗里着迷")
        r2 = cached.search("暗里着迷")
        assert r2 is r1

    def test_search_miss_different_query(self, repo):
        cached = CachingSongRepository(repo)
        r1 = cached.search("第一行")
        r2 = cached.search("在一起")
        assert r2 is not r1

    def test_get_lyric_at_time_caches(self, repo):
        cached = CachingSongRepository(repo)
        l1 = cached.get_lyric_at_time(1, 7.5)
        l2 = cached.get_lyric_at_time(1, 7.5)
        assert l2 is l1

    def test_get_lyric_at_time_miss_different_context(self, repo):
        cached = CachingSongRepository(repo)
        l1 = cached.get_lyric_at_time(1, 7.5, context=1)
        l2 = cached.get_lyric_at_time(1, 7.5, context=2)
        assert l2 is not l1

    def test_cache_size_detects_population(self, repo):
        cached = CachingSongRepository(repo)
        assert cached.cache_size == 0
        cached.get_song(1)
        assert cached.cache_size == 1
        cached.get_song(2)
        assert cached.cache_size == 2

    def test_cache_hit_miss_counters(self, repo):
        from prometheus_client import REGISTRY

        cached = CachingSongRepository(repo)
        cached.get_song(1)
        cached.get_song(1)

        hits = REGISTRY.get_sample_value("cache_ops_total", {"method": "get_song", "result": "hit"}) or 0
        misses = REGISTRY.get_sample_value("cache_ops_total", {"method": "get_song", "result": "miss"}) or 0
        assert hits >= 1
        assert misses >= 1