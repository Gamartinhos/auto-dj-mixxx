"""Carregamento e validacao dos perfis de DJ (profiles.json)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("autodj.profiles")


@dataclass(frozen=True)
class Profile:
    id: str
    label: str
    description: str
    genres: tuple[str, ...]
    bpm_min: float
    bpm_max: float
    max_bpm_jump: float
    harmonic_mixing: bool
    energy_variance: float
    bass_swap_probability: float
    fx_build_up_probability: float
    mix_duration_s: tuple[int, int]
    energy_default: int
    energy_curve: str
    ai_persona: str

    def public(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "bpm_range": [self.bpm_min, self.bpm_max],
            "mix_duration_seconds": self.mix_duration_s,
            "energy_default": self.energy_default,
        }


def _parse(pid: str, raw: dict) -> Profile:
    en = raw.get("energy", {})
    lo, hi = raw.get("bpm_range", [100, 140])
    md_lo, md_hi = raw.get("mix_duration_seconds", [30, 90])
    
    return Profile(
        id=pid,
        label=raw.get("label", pid),
        description=raw.get("description", ""),
        genres=tuple(g.lower() for g in raw.get("genres", [])),
        bpm_min=float(lo),
        bpm_max=float(hi),
        max_bpm_jump=float(raw.get("max_bpm_jump", 4)),
        harmonic_mixing=bool(raw.get("harmonic_mixing", True)),
        energy_variance=float(raw.get("energy_variance", 0.2)),
        bass_swap_probability=float(raw.get("bass_swap_probability", 0.5)),
        fx_build_up_probability=float(raw.get("fx_build_up_probability", 0.3)),
        mix_duration_s=(int(md_lo), int(md_hi)),
        energy_default=int(en.get("default", 60)),
        energy_curve=str(en.get("curve", "")),
        ai_persona=str(raw.get("ai_persona", "")),
    )


class ProfileStore:
    def __init__(self, path: Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.profiles: dict[str, Profile] = {pid: _parse(pid, raw) for pid, raw in data["profiles"].items()}
        if not self.profiles:
            raise ValueError("profiles.json sem perfis")
        self.default_id: str = data.get("default") if data.get("default") in self.profiles else next(iter(self.profiles))

    def get(self, pid: str) -> Profile | None:
        return self.profiles.get(pid)

    def public_list(self) -> list[dict]:
        return [p.public() for p in self.profiles.values()]
