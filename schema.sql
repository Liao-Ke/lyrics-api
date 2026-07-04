CREATE TABLE songs (
  id INTEGER PRIMARY KEY,
  title TEXT, title_raw TEXT, version TEXT,
  artist TEXT, group_key TEXT UNIQUE,
  lyricist TEXT, composer TEXT, arranger TEXT,
  has_translation INTEGER, source_file TEXT, json_file TEXT
);

CREATE TABLE lyrics (
  id INTEGER PRIMARY KEY,
  song_id INTEGER REFERENCES songs(id) ON DELETE CASCADE,
  time_sec REAL, time_str TEXT, text TEXT, translation TEXT, seq INTEGER,
  UNIQUE(song_id, seq)
);

CREATE TABLE api_keys (
  key_id TEXT PRIMARY KEY, key_hash TEXT, name TEXT,
  created_at TEXT, revoked_at TEXT, rate_limit_rpm INTEGER DEFAULT 60
);

CREATE TABLE rate_counters (
  key_id TEXT NOT NULL REFERENCES api_keys(key_id) ON DELETE CASCADE,
  request_at REAL NOT NULL,
  PRIMARY KEY (key_id, request_at)
);
CREATE INDEX idx_rate_counters_key_time ON rate_counters(key_id, request_at);

CREATE VIRTUAL TABLE lyrics_fts USING fts5(
  text,
  content=lyrics,
  content_rowid=id,
  tokenize='trigram'
);