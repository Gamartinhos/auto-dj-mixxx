"""Ligacao com o Mixxx: modelo de estado + transporte MIDI (loopMIDI) via mido."""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field

from . import protocol

log = logging.getLogger("autodj.link")

STATE_STALE_AFTER_S = 2.0


@dataclass
class DeckState:
    playing: bool = False
    pos: float = 0.0          # 0..1
    dur: float = 0.0          # segundos
    bpm: float = 0.0          # BPM efetivo (com pitch/sync)
    file_bpm: float = 0.0     # BPM da faixa no arquivo
    loaded: bool = False
    volume: float = 1.0
    sync: bool = False

    @property
    def remaining(self) -> float:
        return max(0.0, (1.0 - self.pos) * self.dur) if self.dur > 0 else 0.0

    @property
    def elapsed(self) -> float:
        return max(0.0, self.pos * self.dur)

    def to_dict(self) -> dict:
        return {
            "playing": self.playing,
            "pos": round(self.pos, 3),
            "dur": round(self.dur, 1),
            "remaining": round(self.remaining, 1),
            "bpm": round(self.bpm, 1),
            "file_bpm": round(self.file_bpm, 1),
            "loaded": self.loaded,
            "volume": round(self.volume, 2),
            "sync": self.sync,
        }


@dataclass
class MixxxState:
    autodj: bool = False
    transition: float = 0.0
    crossfader: float = 0.0
    decks: list[DeckState] = field(default_factory=lambda: [DeckState(), DeckState()])
    updated_at: float = 0.0   # time.monotonic() da ultima mensagem

    @classmethod
    def from_wire(cls, payload: dict) -> "MixxxState":
        decks = []
        for d in payload.get("d", [])[:2]:
            decks.append(
                DeckState(
                    playing=bool(d.get("pl")),
                    pos=float(d.get("pos", 0.0)),
                    dur=float(d.get("dur", 0.0)),
                    bpm=float(d.get("bpm", 0.0)),
                    file_bpm=float(d.get("fb", 0.0)),
                    loaded=bool(d.get("ld")),
                    volume=float(d.get("vol", 1.0)),
                    sync=bool(d.get("sy")),
                )
            )
        while len(decks) < 2:
            decks.append(DeckState())
        return cls(
            autodj=bool(payload.get("adj")),
            transition=float(payload.get("tr", 0.0)),
            crossfader=float(payload.get("cf", 0.0)),
            decks=decks,
            updated_at=time.monotonic(),
        )

    def to_dict(self) -> dict:
        return {
            "autodj": self.autodj,
            "transition": self.transition,
            "crossfader": round(self.crossfader, 2),
            "decks": [d.to_dict() for d in self.decks],
            "age_s": round(time.monotonic() - self.updated_at, 2) if self.updated_at else None,
        }


class Link:
    """Interface comum (MIDI real e simulador)."""

    kind = "base"

    def start(self) -> None: ...
    def close(self) -> None: ...

    @property
    def connected(self) -> bool:
        return False

    @property
    def state(self) -> MixxxState:
        raise NotImplementedError

    @property
    def fresh(self) -> bool:
        st = self.state
        return st.updated_at > 0 and (time.monotonic() - st.updated_at) < STATE_STALE_AFTER_S

    def send(self, name: str, value: float = 1.0) -> None:
        raise NotImplementedError

    def reconnect(self) -> None:
        """Chamado periodicamente pelo cerebro enquanto desconectado."""

    # ---- atalhos de alto nivel ------------------------------------------
    def set_eq(self, deck: int, low: float | None = None, mid: float | None = None, high: float | None = None) -> None:
        for band, v in (("low", low), ("mid", mid), ("high", high)):
            if v is not None:
                self.send(f"d{deck}_eq_{band}", v)

    def set_filter(self, deck: int, v: float) -> None:
        self.send(f"d{deck}_filter", v)

    def reset_deck_fx(self, deck: int) -> None:
        for band in ("low", "mid", "high"):
            self.send(f"d{deck}_kill_{band}", 0)
            self.send(f"d{deck}_eq_{band}", 0.5)
        self.send(f"d{deck}_filter", 0.5)
        self.send(f"d{deck}_volume", 1.0)

    def request_state(self) -> None:
        self.send("request_state")


class MidiLink(Link):
    """Python <-> Mixxx por UMA porta loopMIDI (o mesmo nome em entrada e saida).

    Eco: o que escrevemos volta na nossa propria entrada, e o SysEx do Mixxx tambem
    chega no proprio Mixxx. Por isso: o Python so processa SysEx; o JS do Mixxx so
    reage a CC mapeados.
    """

    kind = "midi"

    def __init__(self, port_hint: str = "AutoDJ") -> None:
        self.port_hint = port_hint
        self._out = None
        self._in = None
        self._port_name: str | None = None
        self._lock = threading.Lock()
        self._state = MixxxState()
        self._last_sent: dict[str, int] = {}
        self._last_open_try = 0.0
        self.rx_count = 0
        self.tx_count = 0
        self.parse_errors = 0

    # ---- ciclo de vida -----------------------------------------------------
    def start(self) -> None:
        self._try_open()

    def reconnect(self) -> None:
        if self.connected or time.monotonic() - self._last_open_try < 3.0:
            return
        self._try_open()

    def _find(self, names: list[str]) -> str | None:
        hint = self.port_hint.lower()
        for n in names:
            if hint in n.lower():
                return n
        return None

    def _try_open(self) -> None:
        self._last_open_try = time.monotonic()
        try:
            import mido

            out_name = self._find(mido.get_output_names())
            in_name = self._find(mido.get_input_names())
        except Exception as exc:  # backend rtmidi ausente etc.
            log.error("mido/rtmidi indisponivel: %s", exc)
            return
        if not out_name or not in_name:
            log.warning(
                "Porta MIDI contendo '%s' nao encontrada (crie a porta no loopMIDI). Portas: out=%s in=%s",
                self.port_hint, mido.get_output_names(), mido.get_input_names(),
            )
            return
        try:
            self._out = mido.open_output(out_name)
            self._in = mido.open_input(in_name, callback=self._on_message)
            self._port_name = out_name
            log.info("Ponte MIDI aberta: saida='%s' entrada='%s'", out_name, in_name)
            self._last_sent.clear()
            self.request_state()
        except Exception as exc:
            log.error("Falha ao abrir porta MIDI '%s': %s", out_name, exc)
            self.close()

    def close(self) -> None:
        for port in (self._in, self._out):
            try:
                if port is not None:
                    port.close()
            except Exception:  # noqa: BLE001
                pass
        self._in = None
        self._out = None
        self._port_name = None

    @property
    def connected(self) -> bool:
        return self._out is not None and self._in is not None

    @property
    def port_name(self) -> str | None:
        return self._port_name

    # ---- RX ----------------------------------------------------------------
    def _on_message(self, msg) -> None:
        if msg.type != "sysex":
            return  # eco dos nossos proprios CC
        data = bytes(msg.data)
        if not data or data[0] != protocol.SYSEX_MANUFACTURER:
            return
        try:
            payload = json.loads(data[1:].decode("ascii"))
            new_state = MixxxState.from_wire(payload)
        except Exception as exc:  # noqa: BLE001 - nunca deixar a thread MIDI morrer
            self.parse_errors += 1
            log.debug("SysEx invalido (%s): %r", exc, data[:60])
            return
        with self._lock:
            self._state = new_state
            self.rx_count += 1

    @property
    def state(self) -> MixxxState:
        with self._lock:
            return self._state

    # ---- TX ----------------------------------------------------------------
    def send(self, name: str, value: float = 1.0) -> None:
        cmd = protocol.BY_NAME[name]
        data = protocol.encode(cmd, value)
        # EQ/filtro sao enviados dezenas de vezes por segundo: so manda se mudou.
        if cmd.kind in ("param", "range") and self._last_sent.get(name) == data:
            return
        if self._out is None:
            return
        try:
            import mido

            self._out.send(
                mido.Message("control_change", channel=protocol.MIDI_CHANNEL, control=cmd.cc, value=data)
            )
            self._last_sent[name] = data
            self.tx_count += 1
        except Exception as exc:  # noqa: BLE001
            log.error("Erro ao enviar '%s': %s - fechando ponte", name, exc)
            self.close()
