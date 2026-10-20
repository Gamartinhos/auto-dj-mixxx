"""Acesso SOMENTE LEITURA a biblioteca do Mixxx (mixxxdb.sqlite)."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path

log = logging.getLogger("autodj.library")

# ChromaticKey do Mixxx (key_id) -> notacao Camelot
_CAMELOT = {
    1: "8B", 2: "3B", 3: "10B", 4: "5B", 5: "12B", 6: "7B",
    7: "2B", 8: "9B", 9: "4B", 10: "11B", 11: "6B", 12: "1B",
    13: "5A", 14: "12A", 15: "7A", 16: "2A", 17: "9A", 18: "4A",
    19: "11A", 20: "6A", 21: "1A", 22: "8A", 23: "3A", 24: "10A",
}


def camelot_from_key_id(key_id: int | None) -> str | None:
    return _CAMELOT.get(int(key_id or 0))


@dataclass
class TrackInfo:
    id: int
    artist: str
    title: str
    genre: str
    bpm: float
    key: str | None  # Camelot, ex "8A"
    duration: float
    path: str = ""

    @property
    def label(self) -> str:
        return f"{self.artist} - {self.title}".strip(" -") or f"track#{self.id}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["label"] = self.label
        return d


_SELECT = """
SELECT l.id, COALESCE(l.artist,''), COALESCE(l.title,''), COALESCE(l.genre,''),
       COALESCE(l.bpm,0), COALESCE(l.key_id,0), COALESCE(l.duration,0),
       COALESCE(tl.location,'')
FROM library l LEFT JOIN track_locations tl ON tl.id = l.location
"""


def _row(r) -> TrackInfo:
    return TrackInfo(
        id=r[0], artist=r[1], title=r[2], genre=r[3], bpm=float(r[4]),
        key=camelot_from_key_id(r[5]), duration=float(r[6]), path=r[7],
    )


class MixxxLibrary:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection | None:
        if not self.db_path.exists():
            return None
        # mode=ro: nunca escrevemos no banco do Mixxx (ele esta aberto e e dono dele).
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=1.0)
        conn.execute("PRAGMA query_only=ON")
        return conn

    def _query(self, sql: str, params: tuple = ()) -> list[tuple]:
        try:
            conn = self._connect()
            if conn is None:
                return []
            try:
                return conn.execute(sql, params).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            log.warning("Leitura da biblioteca falhou: %s", exc)
            return []

    @property
    def available(self) -> bool:
        return self.db_path.exists()

    def track_count(self) -> int:
        rows = self._query("SELECT COUNT(*) FROM library WHERE mixxx_deleted=0")
        return int(rows[0][0]) if rows else 0

    def autodj_queue(self, limit: int = 8) -> list[TrackInfo]:
        """Fila atual do Auto DJ, em ordem."""
        rows = self._query(
            _SELECT
            + """ JOIN PlaylistTracks pt ON pt.track_id = l.id
                  JOIN Playlists p ON p.id = pt.playlist_id
                  WHERE p.name = 'Auto DJ' AND l.mixxx_deleted = 0
                  ORDER BY pt.position LIMIT ?""",
            (limit,),
        )
        return [_row(r) for r in rows]

    def find_playing(self, duration: float, file_bpm: float) -> TrackInfo | None:
        """Identifica a faixa tocando num deck pela duracao (+-1.5s) e BPM do arquivo."""
        if duration <= 0:
            return None
        rows = self._query(
            _SELECT + " WHERE l.mixxx_deleted=0 AND ABS(l.duration - ?) < 1.5", (duration,)
        )
        if not rows:
            return None
        tracks = [_row(r) for r in rows]
        if file_bpm > 0:
            tracks.sort(key=lambda t: (abs(t.bpm - file_bpm), abs(t.duration - duration)))
        else:
            tracks.sort(key=lambda t: abs(t.duration - duration))
        return tracks[0]

    def search_tracks(self, genre_like: str, min_bpm: float, max_bpm: float, limit: int = 5) -> list[TrackInfo]:
        rows = self._query(
            _SELECT + " WHERE l.mixxx_deleted=0 AND l.bpm >= ? AND l.bpm <= ? AND l.genre LIKE ? ORDER BY RANDOM() LIMIT ?",
            (min_bpm, max_bpm, f"%{genre_like}%", limit)
        )
        return [_row(r) for r in rows]
