#!/usr/bin/env python3
"""将清洗后的 JSON 歌词导入 SQLite 数据库"""

import json
import os
import sqlite3
import time
from collections import Counter
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent

DATABASE_PATH = os.environ.get("DATABASE_PATH", str(_BASE / "data" / "lyrics.db"))
DATA_DIR = _BASE / "data" / "songs"
SCHEMA_PATH = _BASE / "schema.sql"

DROP_ORDER = ("lyrics_fts", "rate_counters", "api_keys", "lyrics", "songs")


def main():
    start = time.time()

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    json_files = sorted(DATA_DIR.glob("*.json"))

    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA foreign_keys = OFF")
    for table in DROP_ORDER:
        cur.execute(f"DROP TABLE IF EXISTS {table}")
    cur.executescript(schema)
    cur.execute("PRAGMA foreign_keys = ON")

    song_count = 0
    lyric_count = 0
    seen_gk: Counter = Counter()
    conn.execute("BEGIN")

    for json_path in json_files:
        with open(json_path, "r", encoding="utf-8") as f:
            song_data = json.load(f)

        writers = song_data.get("writers", {})
        group_key = song_data.get("group_key")
        if group_key:
            seen_gk[group_key] += 1
            if seen_gk[group_key] > 1:
                group_key = f"{group_key}|{seen_gk[group_key]}"

        cur.execute(
            """INSERT INTO songs
               (title, title_raw, version, artist, group_key,
                lyricist, composer, arranger,
                has_translation, source_file, json_file)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                song_data.get("title"),
                song_data.get("title_raw"),
                song_data.get("version"),
                song_data.get("artist"),
                group_key,
                writers.get("lyricist"),
                writers.get("composer"),
                writers.get("arranger"),
                1 if song_data.get("has_translation") else 0,
                song_data.get("source_file"),
                json_path.name,
            ),
        )
        song_id = cur.lastrowid

        lyrics = song_data.get("lyrics", [])
        lyric_rows = [
            (
                song_id,
                entry.get("time"),
                entry.get("time_str"),
                entry.get("text"),
                entry.get("translation"),
                seq,
            )
            for seq, entry in enumerate(lyrics)
        ]
        if lyric_rows:
            cur.executemany(
                "INSERT INTO lyrics (song_id, time_sec, time_str, text, translation, seq) VALUES (?, ?, ?, ?, ?, ?)",
                lyric_rows,
            )
        song_count += 1
        lyric_count += len(lyric_rows)

    cur.execute("INSERT INTO lyrics_fts(lyrics_fts) VALUES ('rebuild')")
    conn.commit()

    elapsed = time.time() - start
    print(f"导入完成: {song_count} 首歌, {lyric_count} 行歌词")
    print(f"耗时: {elapsed:.2f}s")


if __name__ == "__main__":
    main()