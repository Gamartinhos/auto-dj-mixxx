"""Protocolo MIDI entre o cerebro Python e o Mixxx.

Fonte unica da verdade: a tabela COMMANDS abaixo. O script
`tools/generate_mapping.py` gera dela o mapeamento XML + o JS do Mixxx,
e `autodj/mixxx_link.py` usa a mesma tabela para codificar os comandos.

Transporte:
  * Python -> Mixxx : MIDI Control Change, canal 1 (status 0xB0), CC = id do comando.
  * Mixxx -> Python : SysEx  F0 7D <JSON em ASCII 7-bit> F7  (estado, ~4x por segundo).
"""
from __future__ import annotations

from dataclasses import dataclass

MIDI_CHANNEL = 0          # canal 1 (mido conta de 0)
CC_STATUS = 0xB0
SYSEX_MANUFACTURER = 0x7D  # ID "educacional / nao comercial" da especificacao MIDI

# kinds:
#   bool    -> 0/127  => setValue 0/1
#   trigger -> 127    => setValue 1 (e volta a 0)
#   param   -> 0..127 => setParameter 0.0..1.0 (64 = exatamente 0.5, neutro de EQ)
#   range   -> 0..127 => setValue lo..hi        (64 = ponto medio exato)
#   int     -> 0..127 => setValue int
#   offset64-> 0..127 => setValue (valor - 64)  (permite valores negativos)


@dataclass(frozen=True)
class Command:
    name: str
    cc: int
    group: str
    key: str
    kind: str
    lo: float = 0.0
    hi: float = 1.0
    use_parameter: bool = False  # True: engine.setParameter (escala normalizada)


def _deck_commands(deck: int) -> list[Command]:
    base = 0x10 if deck == 1 else 0x30
    ch = f"[Channel{deck}]"
    eq = f"[EqualizerRack1_[Channel{deck}]_Effect1]"
    qe = f"[QuickEffectRack1_[Channel{deck}]]"
    d = f"d{deck}_"
    return [
        Command(d + "play", base + 0, ch, "play", "bool"),
        Command(d + "sync", base + 1, ch, "sync_enabled", "bool"),
        Command(d + "load", base + 2, ch, "LoadSelectedTrack", "trigger"),
        Command(d + "eq_low", base + 3, eq, "parameter1", "param", use_parameter=True),
        Command(d + "eq_mid", base + 4, eq, "parameter2", "param", use_parameter=True),
        Command(d + "eq_high", base + 5, eq, "parameter3", "param", use_parameter=True),
        Command(d + "kill_low", base + 6, eq, "button_parameter1", "bool"),
        Command(d + "kill_mid", base + 7, eq, "button_parameter2", "bool"),
        Command(d + "kill_high", base + 8, eq, "button_parameter3", "bool"),
        Command(d + "filter", base + 9, qe, "super1", "param", use_parameter=True),
        Command(d + "volume", base + 10, ch, "volume", "param", use_parameter=True),
        Command(d + "cue", base + 11, ch, "cue_default", "trigger"),
        Command(d + "pfl", base + 12, ch, "pfl", "bool"),
        Command(d + "eject", base + 13, ch, "eject", "trigger"),
        Command(d + "load_play", base + 14, ch, "LoadSelectedTrackAndPlay", "trigger"),
    ]


COMMANDS: list[Command] = (
    _deck_commands(1)
    + _deck_commands(2)
    + [
        Command("crossfader", 0x60, "[Master]", "crossfader", "range", -1.0, 1.0),
        Command("autodj_enable", 0x61, "[AutoDJ]", "enabled", "bool"),
        Command("autodj_fade_now", 0x62, "[AutoDJ]", "fade_now", "trigger"),
        Command("autodj_skip_next", 0x63, "[AutoDJ]", "skip_next", "trigger"),
        Command("autodj_shuffle", 0x64, "[AutoDJ]", "shuffle_playlist", "trigger"),
        Command("autodj_add_random", 0x65, "[AutoDJ]", "add_random_track", "trigger"),
        Command("autodj_transition", 0x66, "[AutoDJ]", "transition", "offset64"),
        Command("request_state", 0x7E, "[Master]", "", "trigger"),
    ]
)

BY_NAME: dict[str, Command] = {c.name: c for c in COMMANDS}
BY_CC: dict[int, Command] = {c.cc: c for c in COMMANDS}

assert len(BY_NAME) == len(COMMANDS), "nomes de comando duplicados"
assert len(BY_CC) == len(COMMANDS), "CC duplicado na tabela de comandos"


def encode(cmd: Command, value: float = 1.0) -> int:
    """Converte um valor logico no byte de dados MIDI (0..127)."""
    if cmd.kind == "bool":
        return 127 if value else 0
    if cmd.kind == "trigger":
        return 127
    if cmd.kind in ("param", "range"):
        lo, hi = (0.0, 1.0) if cmd.kind == "param" else (cmd.lo, cmd.hi)
        frac = (float(value) - lo) / (hi - lo)
        return max(0, min(127, round(frac * 127)))
    if cmd.kind == "int":
        return max(0, min(127, int(value)))
    if cmd.kind == "offset64":
        return max(0, min(127, int(round(value)) + 64))
    raise ValueError(f"kind desconhecido: {cmd.kind}")
