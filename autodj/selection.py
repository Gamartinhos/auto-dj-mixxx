"""Pontuacao de compatibilidade entre faixas (BPM, tom Camelot, genero, energia)."""
from __future__ import annotations

from .library import TrackInfo
from .profiles import Profile


def camelot_distance(a: str | None, b: str | None) -> int | None:
    """Distancia na roda Camelot: 0 = mesmo tom, 1 = vizinho/relativo (harmonico)."""
    if not a or not b:
        return None
    try:
        na, la = int(a[:-1]), a[-1]
        nb, lb = int(b[:-1]), b[-1]
    except ValueError:
        return None
    steps = min((na - nb) % 12, (nb - na) % 12)
    return steps + (0 if la == lb else 1)


def bpm_gap(a: float, b: float) -> float:
    """Diferenca de BPM considerando half/double time (ex. 64 vs 128)."""
    if a <= 0 or b <= 0:
        return 0.0
    return min(abs(a - b), abs(a * 2 - b), abs(a - b * 2))


def estimate_energy(t: TrackInfo) -> float:
    """Proxy cru de energia 0..100 so por BPM (o Mixxx nao analisa energia)."""
    if t.bpm <= 0:
        return 50.0
    return max(0.0, min(100.0, (t.bpm - 90.0) * 2.2))


def score_transition(cur: TrackInfo | None, nxt: TrackInfo, profile: Profile, energy_target: int) -> tuple[float, list[str]]:
    """Retorna (0..1, motivos). 1 = encaixe perfeito para o perfil atual."""
    notes: list[str] = []
    score = 1.0

    # BPM dentro da faixa do perfil
    if nxt.bpm > 0 and not (profile.bpm_min - 2 <= nxt.bpm <= profile.bpm_max + 2):
        score -= 0.30
        notes.append(f"BPM {nxt.bpm:.0f} fora da faixa {profile.bpm_min:.0f}-{profile.bpm_max:.0f}")

    # salto de BPM em relacao a faixa atual
    if cur and cur.bpm > 0 and nxt.bpm > 0:
        gap = bpm_gap(cur.bpm, nxt.bpm)
        if gap > profile.max_bpm_jump:
            score -= min(0.40, 0.08 * (gap - profile.max_bpm_jump) + 0.15)
            notes.append(f"salto de BPM {gap:.0f}")

    # tom harmonico
    if profile.harmonic_mixing and cur:
        d = camelot_distance(cur.key, nxt.key)
        if d is None:
            score -= 0.05
        elif d >= 3:
            score -= 0.25
            notes.append(f"tons distantes {cur.key}->{nxt.key}")
        elif d == 2:
            score -= 0.10

    # genero
    if nxt.genre and profile.genres:
        g = nxt.genre.lower()
        if not any(pg in g or g in pg for pg in profile.genres):
            score -= 0.15
            notes.append(f"genero '{nxt.genre}' fora do perfil")

    # energia
    e_gap = abs(estimate_energy(nxt) - energy_target)
    if e_gap > 45:
        score -= 0.10
        notes.append("energia distante do alvo")

    return max(0.0, min(1.0, score)), notes
