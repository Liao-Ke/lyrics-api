#!/usr/bin/env python3
"""吊销 API key"""

import os
import sqlite3
import sys
from pathlib import Path

from app.logging import setup_logging, logger

_BASE = Path(__file__).resolve().parent.parent
DATABASE_PATH = os.environ.get("DATABASE_PATH", str(_BASE / "data" / "lyrics.db"))


def main():
    setup_logging()

    if len(sys.argv) < 2:
        print("Usage: python scripts/revoke_key.py <key_id>")
        sys.exit(1)

    key_id = sys.argv[1].strip()

    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.execute("UPDATE api_keys SET revoked_at = datetime('now') WHERE key_id = ? AND revoked_at IS NULL", (key_id,))
    conn.commit()
    conn.close()

    if cur.rowcount == 0:
        print(f"Key '{key_id}' not found or already revoked.")
        sys.exit(1)

    logger.info("audit", event="key_revoked", key_id=key_id)
    print(f"Key '{key_id}' revoked.")


if __name__ == "__main__":
    main()