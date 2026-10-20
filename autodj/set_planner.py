import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
from .transitions import TransitionPlan, beats_to_seconds

log = logging.getLogger("autodj.set_planner")

@dataclass
class PlannedTransition:
    from_artist: str
    from_title: str
    to_artist: str
    to_title: str
    overlap_beats: int
    eq_style: str
    filter_sweep: bool
    note: str

class SetPlanner:
    def __init__(self, sets_dir: Path):
        self.sets_dir = sets_dir
        self.sets_dir.mkdir(exist_ok=True)
        self.active_plan_path = self.sets_dir / "active_set.json"
        self.transitions: List[PlannedTransition] = []
        self._last_mtime = 0.0
        
    def _match_string(self, query: str, target: str) -> bool:
        """Fuzzy match simples: ignora case e espacos vazios"""
        if not query or not target:
            return False
        q = query.lower().replace(" ", "")
        t = target.lower().replace(" ", "")
        return q in t or t in q

    def reload_if_changed(self):
        if not self.active_plan_path.exists():
            if self.transitions:
                log.info("Arquivo de set removido, limpando transições pré-programadas.")
                self.transitions.clear()
            return

        mtime = self.active_plan_path.stat().st_mtime
        if mtime <= self._last_mtime:
            return

        self._last_mtime = mtime
        try:
            with open(self.active_plan_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.transitions.clear()
            for t in data.get("transitions", []):
                self.transitions.append(PlannedTransition(
                    from_artist=t.get("from_artist", ""),
                    from_title=t.get("from_title", ""),
                    to_artist=t.get("to_artist", ""),
                    to_title=t.get("to_title", ""),
                    overlap_beats=t.get("overlap_beats", 32),
                    eq_style=t.get("eq_style", "bass_swap"),
                    filter_sweep=t.get("filter_sweep", False),
                    note=t.get("note", "Transição pré-programada")
                ))
            log.info(f"Set pre-programado carregado: {len(self.transitions)} transições prontas.")
        except Exception as e:
            log.error(f"Erro ao carregar {self.active_plan_path}: {e}")

    def find_plan(self, current, next_track, deck_bpm: float, max_overlap_s: float) -> Optional[TransitionPlan]:
        self.reload_if_changed()
        if not current or not next_track:
            return None

        for pt in self.transitions:
            # Checa se combina com a musica atual e a proxima
            if self._match_string(pt.from_artist, current.artist) and self._match_string(pt.from_title, current.title):
                if self._match_string(pt.to_artist, next_track.artist) and self._match_string(pt.to_title, next_track.title):
                    
                    overlap_s = beats_to_seconds(pt.overlap_beats, deck_bpm, max_overlap_s)
                    log.info(f"ACHEI TRANSIÇÃO PROGRAMADA: {pt.from_title} -> {pt.to_title}")
                    return TransitionPlan(
                        overlap_beats=pt.overlap_beats,
                        overlap_s=overlap_s,
                        eq_style=pt.eq_style,
                        filter_sweep=pt.filter_sweep,
                        keep_next=True,
                        note=pt.note,
                        source="programmed"
                    )
        return None
