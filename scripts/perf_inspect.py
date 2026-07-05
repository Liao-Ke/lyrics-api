#!/usr/bin/env python3
"""FTS5 查询计划分析 + 代表性查询计时。

直接连接 SQLite 数据库运行 EXPLAIN QUERY PLAN 和计时，输出到 stdout。

用法：
  python scripts/perf_inspect.py
  python scripts/perf_inspect.py --db data/lyrics.db
"""

import argparse
import sqlite3
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="FTS5 查询计划分析")
    parser.add_argument("--db", default=None, help="SQLite 数据库路径（默认 data/lyrics.db）")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    db_path = args.db or str(base / "data" / "lyrics.db")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA query_only = 1")

    queries = [
        ("list_songs (page 1, no filter)", "SELECT * FROM songs ORDER BY title LIMIT 20 OFFSET 0"),
        ("list_songs (filter title)", "SELECT * FROM songs WHERE title LIKE '%暗里%' ORDER BY title"),
        ("get_song by id", "SELECT * FROM songs WHERE id = 42"),
        ("get_lyrics by song_id", "SELECT * FROM lyrics WHERE song_id = 42 ORDER BY seq"),
        ("get_lyric_at_time (context=1)", "SELECT * FROM lyrics WHERE song_id = 42 AND time_sec <= 30.0 ORDER BY time_sec DESC LIMIT 3"),
        ("search title (LIKE)", "SELECT * FROM songs WHERE title LIKE '%暗里着迷%'"),
        ("search artist (LIKE)", "SELECT * FROM songs WHERE artist LIKE '%刘德华%'"),
        ("search lyrics (FTS5, long query, 4+ chars)", "SELECT s.* FROM songs s JOIN lyrics_fts ON lyrics_fts.rowid = s.id WHERE lyrics_fts MATCH '暗里着迷'"),
        ("search lyrics (FTS5, short query, 2 chars→LIKE fallback)", "SELECT s.* FROM songs s JOIN lyrics_fts ON lyrics_fts.rowid = s.id WHERE lyrics_fts MATCH '爱你'"),
        ("search multi-scope (title + lyrics)", "SELECT DISTINCT s.* FROM songs s LEFT JOIN lyrics_fts ON lyrics_fts.rowid = s.id WHERE s.title LIKE '%暗里%' OR lyrics_fts MATCH '暗里'"),
    ]

    for name, sql in queries:
        print(f"=== {name} ===")
        print(f"SQL: {sql}")

        try:
            plan = conn.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
            print("  QUERY PLAN:")
            for row in plan:
                print(f"    {row[0]}|{row[1]}|{row[2]}|{row[3]}")
        except Exception as e:
            print(f"  QUERY PLAN ERROR: {e}")

        try:
            n = 50
            start = time.time()
            for _ in range(n):
                conn.execute(sql).fetchall()
            avg = (time.time() - start) / n * 1000
            print(f"  Avg: {avg:.2f}ms ({n} runs)")
        except Exception as e:
            print(f"  TIMING ERROR: {e}")

        print()

    conn.close()


if __name__ == "__main__":
    main()