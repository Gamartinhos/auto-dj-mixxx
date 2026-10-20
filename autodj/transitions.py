"""Plano de transicao e coreografia de EQ/filtro durante o blend."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, asdict
from typing import Callable

from .mixxx_link import Link
from .profiles import Profile

log = logging.getLogger("autodj.transitions")

TICK_S = 0.05  # 20 Hz: suave e leve para o MIDI


@dataclass
class TransitionPlan:
    overlap_beats: int
    overlap_s: float
    eq_style: str
    filter_sweep: bool
    keep_next: bool = True
    note: str = ""
    source: str = "heuristic"  # heuristic | ai

    def to_dict(self) -> dict:
        d = asdict(self)
        d["overlap_s"] = round(self.overlap_s, 1)
        return d


def beats_to_seconds(beats: int, bpm: float, max_s: float) -> float:
    bpm = bpm if bpm and bpm > 40 else 124.0
    return max(2.0, min(max_s, beats * 60.0 / bpm))


def default_plan(profile: Profile, bpm: float, max_overlap_s: float) -> TransitionPlan:
    import random
    
    # Roll transition style
    style = "bass_swap" if random.random() < profile.bass_swap_probability else "smooth_blend"
    use_filter = random.random() < profile.fx_build_up_probability
    
    # Roll duration
    duration_s = random.uniform(profile.mix_duration_s[0], profile.mix_duration_s[1])
    overlap_beats = int(duration_s * bpm / 60.0)
    
    return TransitionPlan(
        overlap_beats=overlap_beats,
        overlap_s=min(duration_s, max_overlap_s),
        eq_style=style,
        filter_sweep=use_filter,
        note=f"gerado com variância de {profile.label}",
        source="heuristic",
    )


# ------------------------------------------------------------------ curvas

def _ramp(p: float, a: float, b: float, v0: float, v1: float) -> float:
    """Rampa linear de v0 a v1 entre p=a e p=b (satura fora)."""
    if p <= a:
        return v0
    if p >= b:
        return v1
    return v0 + (v1 - v0) * (p - a) / (b - a)


def curves(style: str, filter_sweep: bool, p: float) -> dict[str, dict[str, float]]:
    """Valores 0..1 (0.5 = neutro) para entrante/sainte no progresso p (0..1)."""
    inc: dict[str, float] = {}
    out: dict[str, float] = {}

    if style == "bass_swap" or style == "filter_sweep":
        # graves da entrante mortos ate a metade; na troca, entrante abre e sainte fecha.
        inc["low"] = _ramp(p, 0.47, 0.53, 0.0, 0.5)
        out["low"] = _ramp(p, 0.47, 0.53, 0.5, 0.0)
        inc["high"] = _ramp(p, 0.0, 0.30, 0.30, 0.5)
        out["high"] = _ramp(p, 0.75, 1.0, 0.5, 0.35)
    elif style == "breakdown_swap":
        # Sainte sustenta peso até 80%; corta seco grave/médio no drop e entrante explode
        inc["low"] = _ramp(p, 0.78, 0.85, 0.0, 0.5)
        out["low"] = _ramp(p, 0.78, 0.85, 0.5, 0.0)
        out["mid"] = _ramp(p, 0.80, 0.88, 0.5, 0.1)
        inc["high"] = _ramp(p, 0.0, 0.25, 0.35, 0.5)
        out["high"] = _ramp(p, 0.85, 1.0, 0.5, 0.2)
    elif style == "stutter_drop":
        # Stutter rítmico no final da sainte (corte pulsante de volume estilo Tom Morello)
        if 0.50 <= p <= 0.88:
            cycle = (p - 0.50) / 0.38 * 4
            is_silent = (cycle % 1.0) > 0.5
            out["vol"] = 0.05 if is_silent else 1.0
            out["low"] = 0.0 if is_silent else 0.5
        elif p > 0.88:
            out["vol"] = 0.0
            out["low"] = 0.0
        inc["low"] = _ramp(p, 0.85, 0.95, 0.0, 0.5)
        inc["vol"] = 1.0
    elif style == "brake_cut":
        # Parada de vinil / Tape Stop: volume e agudo caem a zero antes do corte seco
        out["vol"] = _ramp(p, 0.65, 0.90, 1.0, 0.0)
        out["high"] = _ramp(p, 0.60, 0.88, 0.5, 0.05)
        out["low"] = _ramp(p, 0.65, 0.88, 0.5, 0.0)
        inc["low"] = 0.5 if p >= 0.90 else 0.0
        inc["vol"] = 1.0 if p >= 0.90 else 0.0
    elif style == "wash_out":
        # Sainte vira passa-alta fina e zera; entrante bate no seco com impacto
        out["filter"] = _ramp(p, 0.25, 0.82, 0.5, 0.92)
        out["low"] = _ramp(p, 0.25, 0.78, 0.5, 0.0)
        out["vol"] = _ramp(p, 0.80, 0.94, 1.0, 0.0)
        inc["low"] = _ramp(p, 0.75, 0.88, 0.0, 0.5)
        inc["filter"] = 0.5
        inc["vol"] = 1.0
    elif style == "smooth_blend":
        inc["low"] = _ramp(p, 0.25, 0.75, 0.15, 0.5)
        out["low"] = _ramp(p, 0.25, 0.75, 0.5, 0.15)
        inc["high"] = _ramp(p, 0.0, 0.40, 0.35, 0.5)
        out["high"] = _ramp(p, 0.60, 1.0, 0.5, 0.35)
    # hard_cut: sem EQ

    if filter_sweep and style not in ("wash_out", "filter_sweep"):
        out["filter"] = _ramp(p, 0.35, 1.0, 0.5, 0.88)
        inc["filter"] = _ramp(p, 0.0, 0.60, 0.12, 0.5)

    return {"in": inc, "out": out}


def _apply(link: Link, deck: int, values: dict[str, float]) -> None:
    for band in ("low", "mid", "high"):
        if band in values:
            link.send(f"d{deck}_eq_{band}", values[band])
    if "filter" in values:
        link.send(f"d{deck}_filter", values["filter"])
    if "vol" in values:
        link.send(f"d{deck}_volume", values["vol"])


async def run_choreography(
    link: Link,
    plan: TransitionPlan,
    incoming: int,
    outgoing: int,
    should_stop: Callable[[], bool],
) -> str:
    """Executa o blend. Retorna 'done' ou 'aborted'. Sempre deixa a entrante neutra no fim."""
    if plan.eq_style == "hard_cut" and not plan.filter_sweep:
        return "done"
    duration = max(1.0, plan.overlap_s)
    t0 = time.monotonic()
    log.info("Blend deck%d -> deck%d: %s, %.1fs%s", outgoing, incoming, plan.eq_style, duration,
             " + filtro" if plan.filter_sweep else "")
    result = "done"
    try:
        while True:
            if should_stop():
                result = "aborted"
                break
            p = (time.monotonic() - t0) / duration
            if p >= 1.0:
                break
            c = curves(plan.eq_style, plan.filter_sweep, p)
            _apply(link, incoming, c["in"])
            _apply(link, outgoing, c["out"])
            await asyncio.sleep(TICK_S)
    finally:
        # entrante volta ao neutro; a sainte so e resetada quando parar (cuidado do cerebro)
        link.reset_deck_fx(incoming)
        if result == "aborted":
            link.reset_deck_fx(outgoing)
    return result
