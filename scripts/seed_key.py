#!/usr/bin/env python3
"""生成 API key 并写入 api_keys 表"""

import hashlib
import os
import sqlite3
import secrets
from pathlib import Path

from app.logging import setup_logging, logger

_BASE = Path(__file__).resolve().parent.parent
DATABASE_PATH = os.environ.get("DATABASE_PATH", str(_BASE / "data" / "lyrics.db"))


def main():
    setup_logging()

    name = input("Key name (e.g. dev, friend): ").strip()
    if not name:
        name = "unnamed"

    raw_key = secrets.token_hex(32)
    key_id = secrets.token_hex(8)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute(
        "INSERT INTO api_keys (key_id, key_hash, name, created_at) VALUES (?, ?, ?, datetime('now'))",
        (key_id, key_hash, name),
    )
    conn.commit()
    conn.close()

    logger.info("audit", event="key_issued", key_id=key_id, name=name)

    print(f"API Key: {raw_key}")
    print(f"Key ID: {key_id}")
    print(f"Name: {name}")
    print("Store the key securely — it cannot be retrieved again.")


if __name__ == "__main__":
    main()