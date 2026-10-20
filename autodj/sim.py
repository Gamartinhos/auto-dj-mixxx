"""Mixxx simulado (modo --sim): permite testar cerebro, IA, API e UI sem o Mixxx.

Simula decks, fila do Auto DJ, crossfade e responde aos mesmos comandos do protocolo MIDI.
Tempo real 1x; faixas curtas (45-75 s) para ver varias transicoes em poucos minutos.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time

from . import protocol
from .library import TrackInfo
from .mixxx_link import DeckState, Link, MixxxState

log = logging.getLogger("autodj.sim")

_GENRES = [
    ("melodic house", 122, "8A"), ("progressive house", 124, "9A"), ("tech house", 126, "8A"),
    ("deep house", 120, "7A"), ("house", 123, "9B"), ("bass house", 127, "10A"),
    ("melodic house", 121, "7A"), ("progressive house", 125, "10A"),
    ("reggaeton", 95, "3B"),   # fora de perfil de proposito: testa o "pular"
    ("tech house", 124, "9A"), ("organic house", 119, "6A"), ("techno", 132, "5A"),
]


def make_tracks(n: int = 12, seed: int = 7) -> list[TrackInfo]:
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        genre, bpm, key = _GENRES[i % len(_GENRES)]
        out.append(
            TrackInfo(
                id=i + 1,
                artist=f"[SIM] Artista {i + 1:02d}",
                title=f"Faixa {i + 1:02d}",
                genre=genre,
                bpm=float(bpm + rnd.choice([-1, 0, 0, 1])),
                key=key,
                duration=float(rnd.randint(45, 75)),
                path=f"sim://{i + 1}",
            )
        )
    return out


class SimLibrary:
    available = True

    def __init__(self, link: "SimLink") -> None:
        self._link = link

    def track_count(self) -> int:
        return len(self._link.catalog)

    def autodj_queue(self, limit: int = 8) -> list[TrackInfo]:
        return list(self._link.queue[:limit])

    def find_playing(self, duration: float, file_bpm: float) -> TrackInfo | None:
        best = None
        for t in self._link.catalog:
            if abs(t.duration - duration) < 1.5:
                if best is None or abs(t.bpm - file_bpm) < abs(best.bpm - file_bpm):
                    best = t
        return best


class _SimDeck:
    def __init__(self) -> None:
        self.track: TrackInfo | None = None
        self.pos_s = 0.0
        self.playing = False
        self.volume = 1.0


class SimLink(Link):
    kind = "sim"

    def __init__(self) -> None:
        self.catalog = make_tracks()
        self.queue: list[TrackInfo] = list(self.catalog)
        random.Random(11).shuffle(self.queue)
        self.decks = [_SimDeck(), _SimDeck()]
        self.autodj = False
        self.transition_s = 10.0
        self.crossfader = -1.0
        self.fx: dict[str, float] = {}
        self.sent: list[tuple[str, float]] = []
        self._fade: dict | None = None
        self._task: asyncio.Task | None = None
        self._state = MixxxState()
        self.library = SimLibrary(self)

    # ---- ciclo ------------------------------------------------------------
    def start(self) -> None:
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        log.info("Mixxx SIMULADO ativo (%d faixas)", len(self.catalog))

    def close(self) -> None:
        if self._task:
            self._task.cancel()

    @property
    def connected(self) -> bool:
        return True

    @property
    def state(self) -> MixxxState:
        return self._state

    # ---- comandos ---------------------------------------------------------
    def send(self, name: str, value: float = 1.0) -> None:
        cmd = protocol.BY_NAME[name]
        # passa pela mesma quantizacao 7-bit do MIDI real
        data = protocol.encode(cmd, value)
        self.sent.append((name, value))
        if len(self.sent) > 2000:
            del self.sent[:1000]
        if name == "autodj_enable":
            self.autodj = bool(value)
        elif name == "autodj_transition":
            self.transition_s = float(round(value))
        elif name == "autodj_fade_now":
            self._start_fade(now=True)
        elif name == "autodj_skip_next":
            self._skip_next()
        elif name == "autodj_add_random":
            self.queue.append(random.choice(self.catalog))
        elif name == "autodj_shuffle":
            random.shuffle(self.queue)
        elif name == "request_state":
            self._publish()
        elif name.endswith(("_play",)) and name.startswith("d"):
            self.decks[int(name[1]) - 1].playing = bool(value)
        else:
            self.fx[name] = data / 127.0

    # ---- logica do "Mixxx" ------------------------------------------------
    def _idle_index(self) -> int | None:
        for i, d in enumerate(self.decks):
            if not d.playing:
                return i
        return None

    def _skip_next(self) -> None:
        i = self._idle_index()
        if i is None or not self.queue:
            return
        self.decks[i].track = self.queue.pop(0)
        self.decks[i].pos_s = 0.0

    def _start_fade(self, now: bool = False) -> None:
        if self._fade or not self.autodj:
            return
        playing = [i for i, d in enumerate(self.decks) if d.playing]
        idle = self._idle_index()
        if len(playing) != 1 or idle is None or self.decks[idle].track is None:
            return
        out_i = playing[0]
        dur = max(1.0, self.transition_s)
        self.decks[idle].playing = True
        self._fade = {"out": out_i, "in": idle, "t0": time.monotonic(), "dur": dur}

    async def _run(self) -> None:
        last = time.monotonic()
        while True:
            await asyncio.sleep(0.1)
            now = time.monotonic()
            dt, last = now - last, now
            self._tick(dt, now)
            self._publish()

    def _tick(self, dt: float, now: float) -> None:
        for d in self.decks:
            if d.playing and d.track:
                d.pos_s += dt
                if d.pos_s >= d.track.duration:
                    d.playing = False
                    d.track = None
                    d.pos_s = 0.0
        if self.autodj:
            # carrega faixa na deck ociosa
            for d in self.decks:
                if not d.playing and d.track is None and self.queue:
                    d.track = self.queue.pop(0)
                    d.pos_s = 0.0
            if not any(d.playing for d in self.decks):
                for d in self.decks:
                    if d.track is not None:
                        d.playing = True
                        break
            # dispara fade perto do fim
            if not self._fade:
                for i, d in enumerate(self.decks):
                    if d.playing and d.track and (d.track.duration - d.pos_s) <= self.transition_s:
                        self._start_fade()
        if self._fade:
            f = self._fade
            p = min(1.0, (now - f["t0"]) / f["dur"])
            self.decks[f["out"]].volume = 1.0 - p
            self.decks[f["in"]].volume = p
            self.crossfader = (-1.0 + 2 * p) if f["in"] == 1 else (1.0 - 2 * p)
            if p >= 1.0:
                o = self.decks[f["out"]]
                o.playing = False
                o.track = None
                o.pos_s = 0.0
                o.volume = 1.0
                self.decks[f["in"]].volume = 1.0
                self._fade = None

    def _publish(self) -> None:
        decks = []
        for d in self.decks:
            t = d.track
            decks.append(
                DeckState(
                    playing=d.playing,
                    pos=(d.pos_s / t.duration) if t else 0.0,
                    dur=t.duration if t else 0.0,
                    bpm=t.bpm if t else 0.0,
                    file_bpm=t.bpm if t else 0.0,
                    loaded=t is not None,
                    volume=d.volume,
                )
            )
        self._state = MixxxState(
            autodj=self.autodj,
            transition=self.transition_s,
            crossfader=self.crossfader,
            decks=decks,
            updated_at=time.monotonic(),
        )
