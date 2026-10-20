"""Camada de inteligencia: google-genai.

Backends (AUTODJ_AI_BACKEND):
  gemini : usa google.genai + GEMINI_API_KEY
  ollama : (não suportado atualmente nesta refatoração)
  off    : sem IA - so heuristica
  auto   : gemini se houver chave; senao off

Se a IA falhar/demorar, o cerebro cai na heuristica do perfil: a festa nunca para.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
from typing import Any, Literal

from pydantic import BaseModel, Field

from .config import Config
from .library import TrackInfo
from .profiles import Profile
from .transitions import TransitionPlan, beats_to_seconds

log = logging.getLogger("autodj.ai")


class AIPlan(BaseModel):
    """Schema devolvido pela IA."""

    keep_next: bool = Field(description="false = a proxima musica da fila NAO serve; pule-a")
    overlap_beats: int = Field(description="duracao do blend em beats (8 a 64)")
    eq_style: Literal["bass_swap", "smooth_blend", "filter_sweep", "hard_cut", "breakdown_swap", "stutter_drop", "brake_cut", "wash_out"]
    filter_sweep: bool = Field(description="usar varredura de filtro durante o blend")
    note: str = Field(description="justificativa curta em portugues (max 120 caracteres)")


def _ollama_alive(base_url: str) -> bool:
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    try:
        with urllib.request.urlopen(root + "/api/tags", timeout=1.5) as r:  # noqa: S310 - localhost
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


class DJAgent:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.backend = "off"
        self.status = "desligada"
        self.last_error: str | None = None
        self.calls = 0
        self.failures = 0
        self.last_latency_s: float | None = None
        self._client = None
        self._lock = asyncio.Lock()
        self._persona = ""
        self._brain = None
        self._tools = []
        self._system_instructions = ""

    def bind_brain(self, brain: "Brain") -> None:
        self._brain = brain

    # ------------------------------------------------------------------ ciclo de vida
    def _pick_backend(self) -> str:
        want = self.cfg.ai_backend
        if want == "off":
            return "off"
        if want == "gemini":
            return "gemini" if self.cfg.gemini_api_key else "off"
        if want == "ollama":
            return "ollama"
        # auto
        if self.cfg.gemini_api_key:
            return "gemini"
        if _ollama_alive(self.cfg.ollama_url):
            return "ollama"
        return "off"

    def _build_tools(self):
        custom = []
        if self._brain:
            def search_local_library(genre: str, min_bpm: float, max_bpm: float) -> str:
                """Busca faixas na biblioteca local do Mixxx (SQLite) que combinam com o gênero e BPM.
                Use isso para curar a próxima faixa da fila se a fila atual estiver pequena."""
                tracks = self._brain.library.search_tracks(genre, min_bpm, max_bpm, limit=5)
                if not tracks:
                    return f"[Biblioteca] Nenhuma faixa encontrada para {genre} entre {min_bpm}-{max_bpm} BPM."
                out = f"[Biblioteca] Faixas encontradas para {genre} entre {min_bpm}-{max_bpm} BPM:\\n"
                for i, t in enumerate(tracks, 1):
                    out += f"{i}. {t.label} ({t.bpm:.1f} BPM) - {t.genre} - key: {t.key}\\n"
                return out
                
            def download_track(query: str) -> str:
                """Busca no YouTube e baixa a melhor música encontrada usando yt-dlp, e adiciona à fila.
                O formato deve ser query, ex: 'Vintage Culture and James Hype'.
                Use APENAS se a biblioteca local não tiver opções adequadas."""
                if not self._brain.allow_downloads:
                    return "ERRO: O DJ desativou a permissão de downloads (allow_downloads=False). Escolha uma faixa da biblioteca local com a ferramenta search_local_library."
                import subprocess
                from pathlib import Path
                download_dir = Path.home() / "Music" / "AutoDJ_Downloads"
                download_dir.mkdir(parents=True, exist_ok=True)
                
                cmd = [
                    "yt-dlp",
                    f"ytsearch1:{query}",
                    "--extract-audio",
                    "--audio-format", "mp3",
                    "--output", f"{download_dir}/%(title)s.%(ext)s",
                    "--no-playlist",
                    "--match-filter", "duration < 600"
                ]
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    return f"[yt-dlp] Sucesso! Baixada a faixa correspondente a '{query}'. Ela aparecerá na biblioteca após rescan."
                except subprocess.CalledProcessError as e:
                    return f"ERRO no download: {e.stderr}"
                
            custom.extend([search_local_library, download_track])
        return custom

    async def start(self, persona: str = "") -> None:
        self.backend = self._pick_backend()
        if self.backend == "off":
            self.status = "desligada (sem GEMINI_API_KEY) - usando heuristica"
            log.warning("IA desligada: %s", self.status)
            return
        await self._open(persona)

    async def _open(self, persona: str) -> None:
        from google import genai

        await self._close()
        self._persona = persona
        try:
            if self.backend != "gemini":
                raise ValueError(f"Backend '{self.backend}' is not supported sem google.antigravity.")
            
            self._client = genai.Client(api_key=self.cfg.gemini_api_key)
            self._system_instructions = (
                "Você é o CÉREBRO de um sistema de Auto DJ rodando sobre o Mixxx. "
                "Você NÃO controla o áudio diretamente: apenas decide como a próxima transição deve ser. "
                "Sempre que a fila de reprodução estiver vazia ou terminando, você DEVE usar a ferramenta 'search_local_library' "
                "para encontrar faixas que combinem com a energia e o perfil atual, ou 'download_track' se permitido e necessário. "
                "Responda SEMPRE com o schema JSON pedido no final."
                f"\\n\\nPERSONALIDADE DO DJ ATUAL:\\n{persona}"
            )
            self._tools = self._build_tools()
            
            self.status = f"ativa ({self.backend})"
            self.last_error = None
            log.info("Agente iniciado via google-genai (backend=%s)", self.backend)
        except Exception as exc:  # noqa: BLE001
            self._client = None
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.status = f"erro ao iniciar ({self.backend}) - usando heuristica"
            log.error("Falha ao iniciar agente: %s", self.last_error)

    async def _close(self) -> None:
        self._client = None

    async def stop(self) -> None:
        await self._close()

    async def set_persona(self, persona: str) -> None:
        """Troca de perfil = nova conversa com a nova personalidade."""
        if self.backend != "off" and persona != self._persona:
            await self._open(persona)

    @property
    def active(self) -> bool:
        return self._client is not None

    def info(self) -> dict:
        return {
            "backend": self.backend,
            "active": self.active,
            "status": self.status,
            "calls": self.calls,
            "failures": self.failures,
            "last_latency_s": self.last_latency_s,
            "last_error": self.last_error,
        }

    # ------------------------------------------------------------------ decisao
    async def plan_transition(
        self,
        *,
        profile: Profile,
        energy: int,
        current: TrackInfo | None,
        deck_bpm: float,
        next_track: TrackInfo | None,
        heuristic_score: float,
        heuristic_notes: list[str],
        history: list[str],
        max_overlap_s: float,
    ) -> TransitionPlan | None:
        if not self.active:
            return None
        async with self._lock:
            t0 = time.monotonic()
            self.calls += 1
            try:
                ctx = {
                    "perfil": profile.label,
                    "faixa_bpm": [profile.bpm_min, profile.bpm_max],
                    "energia_alvo_0_100": energy,
                    "curva_de_energia_do_perfil": profile.energy_curve,
                    "faixa_atual": current.to_dict() if current else {"bpm_deck": round(deck_bpm, 1)},
                    "proxima_faixa_na_fila": next_track.to_dict() if next_track else None,
                    "nota_heuristica_0_1": round(heuristic_score, 2),
                    "alertas_heuristica": heuristic_notes,
                    "ultimas_faixas": history[-5:],
                    "padrao_do_perfil": {
                        "mix_duration_s": profile.mix_duration_s,
                        "bass_swap_probability": profile.bass_swap_probability,
                        "fx_build_up_probability": profile.fx_build_up_probability,
                    },
                }
                prompt = (
                    "Decida a proxima transicao. Contexto (JSON):\\n"
                    + json.dumps(ctx, ensure_ascii=False)
                    + "\\n\\nRegras: overlap_beats entre 8 e 64 (multiplos de 8); se keep_next=false a faixa seguinte sera "
                    "pulada (so faca isso se ela realmente nao servir ao perfil/energia). note: max 120 caracteres."
                )
                raw = await asyncio.wait_for(self._ask(prompt), timeout=self.cfg.ai_timeout_s)
                plan = self._to_plan(raw, deck_bpm, max_overlap_s)
                self.last_latency_s = round(time.monotonic() - t0, 2)
                self.last_error = None
                return plan
            except Exception as exc:  # noqa: BLE001 - IA nunca pode derrubar o DJ
                self.failures += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.warning("IA falhou (%s) - usando heuristica", self.last_error)
                return None

    async def _ask(self, prompt: str) -> Any:
        from google.genai import types
        model_name = self.cfg.gemini_model or "gemini-2.5-flash"
        
        config = types.GenerateContentConfig(
            system_instruction=self._system_instructions + "\\nIMPORTANTE: Sua resposta final (após o uso das ferramentas) DEVE ser UM OBJETO JSON puro e válido, seguindo estritamente as chaves: keep_next (bool), overlap_beats (int), eq_style (str: 'bass_swap'|'smooth_blend'|'filter_sweep'|'hard_cut'), filter_sweep (bool), note (str).",
            temperature=0.7,
        )
        if self._tools:
            config.tools = self._tools

        chat = self._client.aio.chats.create(model=model_name, config=config)
        resp = await chat.send_message(prompt)
        
        max_turns = 5
        turns = 0
        while resp.function_calls and turns < max_turns:
            turns += 1
            parts = []
            for fc in resp.function_calls:
                func_name = fc.name
                args = fc.args or {}
                result = ""
                for t in self._tools:
                    if t.__name__ == func_name:
                        try:
                            result = t(**args)
                        except Exception as e:
                            result = f"Error executing {func_name}: {e}"
                        break
                else:
                    result = f"Unknown function: {func_name}"
                
                parts.append(types.Part.from_function_response(
                    name=func_name,
                    response={"result": result}
                ))
            resp = await chat.send_message(parts)
            
        return resp.text

    @staticmethod
    def _to_plan(raw: Any, deck_bpm: float, max_overlap_s: float) -> TransitionPlan:
        if isinstance(raw, BaseModel):
            data = raw.model_dump()
        elif isinstance(raw, str):
            s = raw.strip()
            if "{" in s:
                s = s[s.index("{"): s.rindex("}") + 1]
            data = json.loads(s)
        else:
            data = dict(raw)
        ai = AIPlan.model_validate(data)
        beats = max(8, min(64, round(ai.overlap_beats / 8) * 8 or 8))
        return TransitionPlan(
            overlap_beats=beats,
            overlap_s=beats_to_seconds(beats, deck_bpm, max_overlap_s),
            eq_style=ai.eq_style,
            filter_sweep=ai.filter_sweep,
            keep_next=ai.keep_next,
            note=ai.note[:140],
            source="ai",
        )
