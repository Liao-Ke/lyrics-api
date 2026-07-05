import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.repositories.sqlite_repo import SqliteSongRepository

SCHEMA = (Path(__file__).resolve().parent.parent / "schema.sql").read_text()


@pytest.fixture
def repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)

    conn.executemany(
        "INSERT INTO songs "
        "(title, title_raw, version, artist, group_key, "
        "lyricist, composer, arranger, has_translation, source_file, json_file) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("测试A", "测试A", None, "艺术家1", "测试A|艺术家1",
             "作词人1", "作曲人1", "编曲人1", 0, "a.lrc", "a.json"),
            ("测试B", "测试B（Live）", "Live", "艺术家1", "测试B|艺术家1",
             "作词人2", None, None, 1, "b.lrc", "b.json"),
            ("测试C", "测试C", None, "艺术家2", "测试C|艺术家2",
             "作词人1", "作曲人2", None, 0, "c.lrc", "c.json"),
        ],
    )

    conn.executemany(
        "INSERT INTO lyrics (song_id, time_sec, time_str, text, translation, seq) "
        "VALUES (?,?,?,?,?,?)",
        [
            (1, 0.0, "00:00.000", "第一行", None, 0),
            (1, 5.0, "00:05.000", "暗里着迷", "secretly", 1),
            (1, 10.0, "00:10.000", "第三行", None, 2),
            (2, 0.0, "00:00.000", "B第一行", None, 0),
            (2, 3.0, "00:03.000", "在一起", "together", 1),
            (3, 0.0, "00:00.000", "C歌词", None, 0),
            (3, 1.0, "00:01.000", "暗里着迷", None, 1),
        ],
    )

    conn.execute("INSERT INTO lyrics_fts(lyrics_fts) VALUES ('rebuild')")
    conn.commit()
    conn.close()

    yield SqliteSongRepository(path)

    os.unlink(path)