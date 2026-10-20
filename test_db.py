from pathlib import Path
import os
import sqlite3

def _default_db_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "Mixxx" / "mixxxdb.sqlite"
    return Path.home() / ".mixxx" / "mixxxdb.sqlite"

db = _default_db_path()
print(f"Path: {db}")
print(f"Exists: {db.exists()}")

if db.exists():
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT id, name, hidden FROM Playlists")
        for row in cur.fetchall():
            print(f"Playlist: {row}")
    except Exception as e:
        print(f"Error: {e}")
