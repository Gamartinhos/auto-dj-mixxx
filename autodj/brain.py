"""Cerebro do Auto DJ: observa o Mixxx, planeja transicoes e executa a coreografia.

Divisao de trabalho:
  * Mixxx (AutoDJ nativo) cuida de carregar faixas, tocar e do crossfade em si.
  * Este cerebro decide: QUAL faixa serve (pula as ruins), QUANTO dura o blend e COMO
    ele soa (bass swap / filtro / smooth), e executa o EQ/filtro durante o blend.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

from .ai import DJAgent
from .config import Config
from .library import MixxxLibrary, TrackInfo
from .mixxx_link import DeckState, Link, MixxxState
from .profiles import Profile, ProfileStore
from .selection import score_transition
from .transitions import TransitionPlan, default_plan, run_choreography
from .set_planner import SetPlanner

log = logging.getLogger("autodj.brain")

TICK_S = 0.25
SKIP_THRESHOLD = 0.55     # nota heuristica minima para aceitar a proxima faixa
MAX_SKIPS_PER_TRACK = 3
MIN_QUEUE = 3

EVENTS: deque[dict] = deque(maxlen=300)


class RingHandler(logging.Handler):
    """Guarda os ultimos logs 'autodj.*' para exibir na interface web."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            EVENTS.append(
                {
                    "t": time.strftime("%H:%M:%S", time.localtime(record.created)),
                    "level": record.levelname.lower(),
                    "src": record.name.replace("autodj.", ""),
                    "msg": record.getMessage(),
                }
            )
        except Exception:  # noqa: BLE001
            pass


class Brain:
    def __init__(self, cfg: Config, link: Link, library, store: ProfileStore, agent: DJAgent) -> None:
        self.cfg = cfg
        self.link = link
        self.library: MixxxLibrary = library
        self.store = store
        self.agent = agent
        self.agent.bind_brain(self)

        from .config import ROOT
        self.set_planner = SetPlanner(ROOT / "sets")

        self.autonomous = False
        self.allow_downloads = False
        self.profile: Profile = store.profiles[store.default_id]
        self.energy: int = self.profile.energy_default
        self.phase = "offline"
        self.plan: TransitionPlan | None = None
        self.cur_track: TrackInfo | None = None
        self.next_track: TrackInfo | None = None
        self.queue_cache: list[TrackInfo] = []
        self.history: list[str] = []
        self.transitions_done = 0

        self._track_key: tuple | None = None
        self._planned = False
        self._skips = 0
        self._plan_task: asyncio.Task | None = None
        self._choreo_task: asyncio.Task | None = None
        self._choreo_for: tuple | None = None
        self._dirty = {0: False, 1: False}
        self._last_enable = 0.0
        self._last_refill = 0.0
        self._last_lib = 0.0
        self._last_req = 0.0
        self._last_count = 0.0
        self._lib_count: int | None = None
        self._runner: asyncio.Task | None = None

    # ================================================================ ciclo de vida
    async def start(self) -> None:
        await self.agent.start(self.profile.ai_persona)
        self._runner = asyncio.create_task(self._run(), name="brain")

    async def stop(self) -> None:
        if self._runner:
            self._runner.cancel()
            try:
                await self._runner
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._cancel(self._plan_task)
        self._cancel(self._choreo_task)
        if self.link.connected:
            for i in (1, 2):
                self.link.reset_deck_fx(i)
        await self.agent.stop()

    @staticmethod
    def _cancel(task: asyncio.Task | None) -> None:
        if task and not task.done():
            task.cancel()

    async def _run(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - o cerebro nao pode morrer no meio da festa
                log.exception("Erro no ciclo do cerebro (continuando)")
                await asyncio.sleep(1.0)
            await asyncio.sleep(TICK_S)

    # ================================================================ comandos da API
    def set_autonomous(self, on: bool) -> None:
        if on == self.autonomous:
            return
        self.autonomous = on

    def set_allow_downloads(self, on: bool) -> None:
        if on == self.allow_downloads:
            return
        self.allow_downloads = on
        log.info("Downloads via IA: %s", "Ligados" if on else "Desligados")
        if on:
            log.info("Modo AUTONOMO ligado (perfil: %s, energia %d)", self.profile.label, self.energy)
            self._planned = False
            self._last_enable = 0.0
        else:
            log.info("Modo autonomo desligado - Mixxx segue sem intervencao do cerebro")
            self._cancel(self._plan_task)
            self._cancel(self._choreo_task)
            if self.link.connected:
                for i in (1, 2):
                    self.link.reset_deck_fx(i)
            self._dirty = {0: False, 1: False}

    async def set_profile(self, pid: str) -> bool:
        p = self.store.get(pid)
        if p is None:
            return False
        self.profile = p
        self.energy = p.energy_default
        log.info("Perfil alterado para: %s", p.label)
        self._cancel(self._plan_task)
        self._planned = False
        self._skips = 0
        await self.agent.set_persona(p.ai_persona)
        return True

    def set_energy(self, value: int) -> None:
        self.energy = max(0, min(100, int(value)))
        log.info("Energia alvo da pista: %d", self.energy)
        self._planned = False  # replaneja a transicao atual com o novo humor

    def mix_now(self) -> None:
        if not self.link.state.autodj:
            self.link.send("autodj_enable", 1)
        self.link.send("autodj_fade_now")
        log.info("Mix agora (manual)")

    def skip_next(self) -> None:
        self.link.send("autodj_skip_next")
        self._planned = False
        log.info("Proxima faixa pulada (manual)")

    def add_random(self) -> None:
        self.link.send("autodj_add_random")
        log.info("Faixa aleatoria adicionada a fila (manual)")

    def set_mixxx_autodj(self, on: bool) -> None:
        self.link.send("autodj_enable", 1 if on else 0)
        log.info("Auto DJ do Mixxx: %s", "ligado" if on else "desligado")

    async def trigger_trick(self, name: str) -> dict:
        """Dispara um truque ou gracinha de DJ ao vivo no deck que estiver tocando."""
        st = self.link.state
        playing = [i for i in (0, 1) if st.decks[i].playing]
        if not playing:
            return {"ok": False, "msg": "Nenhum deck tocando no momento"}
        cur_deck = playing[0] + 1  # 1 ou 2

        if name == "kill_bass":
            log.info("FX Ao Vivo: Kill Bass no Deck %d (2s)", cur_deck)
            self.link.send(f"d{cur_deck}_kill_low", 1)
            asyncio.create_task(self._revert_trick(cur_deck, f"d{cur_deck}_kill_low", 0, delay=2.0))
            return {"ok": True, "msg": f"Grave cortado no Deck {cur_deck} por 2s"}

        elif name == "stutter":
            log.info("FX Ao Vivo: Stutter / Killswitch no Deck %d", cur_deck)
            asyncio.create_task(self._run_stutter(cur_deck))
            return {"ok": True, "msg": f"Stutter disparado no Deck {cur_deck}"}

        elif name == "tape_stop":
            log.info("FX Ao Vivo: Tape Stop no Deck %d", cur_deck)
            asyncio.create_task(self._run_tape_stop(cur_deck))
            return {"ok": True, "msg": f"Tape Stop no Deck {cur_deck} e puxando a próxima"}

        elif name == "drop_now":
            log.info("FX Ao Vivo: Drop Agora / Mix Imediato")
            self.mix_now()
            return {"ok": True, "msg": "Drop imediato disparado!"}

        return {"ok": False, "msg": f"Truque desconhecido: {name}"}

    async def _revert_trick(self, deck: int, cmd: str, val: float, delay: float):
        await asyncio.sleep(delay)
        self.link.send(cmd, val)

    async def _run_stutter(self, deck: int):
        for _ in range(4):
            self.link.send(f"d{deck}_volume", 0.0)
            await asyncio.sleep(0.12)
            self.link.send(f"d{deck}_volume", 1.0)
            await asyncio.sleep(0.12)

    async def _run_tape_stop(self, deck: int):
        for step in (0.7, 0.4, 0.15, 0.0):
            self.link.send(f"d{deck}_volume", step)
            await asyncio.sleep(0.12)
        await asyncio.sleep(0.3)
        self.mix_now()
        await asyncio.sleep(0.5)
        self.link.send(f"d{deck}_volume", 1.0)

    # ================================================================ ciclo principal
    async def _tick(self) -> None:
        self.link.reconnect()
        if not self.link.connected:
            self.phase = "offline"
            return
        now = time.monotonic()
        if not self.link.fresh:
            self.phase = "sem_dados"
            if now - self._last_req > 3.0:
                self._last_req = now
                self.link.request_state()
            return

        st = self.link.state
        self._refresh_library(now)
        self._cleanup_fx(st)

        if not self.autonomous:
            self.phase = "manual"
            return

        self._keep_queue(now)

        if not st.autodj:
            self.phase = "ligando_autodj"
            if now - self._last_enable > 3.0:
                self._last_enable = now
                self.link.send("autodj_enable", 1)
                log.info("Ligando o Auto DJ do Mixxx")
            return

        playing = [i for i in (0, 1) if st.decks[i].playing]

        if not playing:
            self.phase = "aguardando_faixa"
            self._track_key = None
        elif len(playing) == 1:
            self._on_solo(st, playing[0])
        else:
            self._on_transition(st)

    # ---------------------------------------------------------------- fases
    def _on_solo(self, st: MixxxState, cur_i: int) -> None:
        d = st.decks[cur_i]
        self._choreo_for = None
        key = (cur_i, round(d.dur, 1))
        if key != self._track_key:
            self._new_track(key, d)
        self.phase = "tocando"
        planning = self._plan_task is not None and not self._plan_task.done()
        if not self._planned and not planning and d.elapsed >= 2.0:
            self._plan_task = asyncio.create_task(self._plan(key, cur_i), name="plan")

    def _new_track(self, key: tuple, d: DeckState) -> None:
        self._cancel(self._plan_task)
        self._track_key = key
        self._planned = False
        self._skips = 0
        self.plan = None
        self.cur_track = self.library.find_playing(d.dur, d.file_bpm)
        label = self.cur_track.label if self.cur_track else f"deck {key[0] + 1} ({d.file_bpm:.0f} BPM, {d.dur:.0f}s)"
        if not self.history or self.history[-1] != label:
            self.history.append(label)
            self.history = self.history[-30:]
        self.transitions_done += 1 if len(self.history) > 1 else 0
        log.info("Tocando agora: %s", label)

    def _on_transition(self, st: MixxxState) -> None:
        self.phase = "transicao"
        self._cancel(self._plan_task)
        d0, d1 = st.decks
        pair = (round(d0.dur, 1), round(d1.dur, 1))
        if self._choreo_for == pair:
            return
        self._choreo_for = pair
        incoming = 1 if d1.elapsed < d0.elapsed else 0
        outgoing = 1 - incoming
        plan = self.plan or default_plan(
            self.profile, st.decks[outgoing].bpm or st.decks[outgoing].file_bpm, self.cfg.max_overlap_s
        )
        self._dirty[incoming] = self._dirty[outgoing] = True
        self._cancel(self._choreo_task)
        self._choreo_task = asyncio.create_task(
            run_choreography(
                self.link, plan, incoming + 1, outgoing + 1,
                should_stop=lambda: (not self.autonomous) or (not self.link.state.decks[outgoing].playing),
            ),
            name="choreo",
        )

    def _cleanup_fx(self, st: MixxxState) -> None:
        busy = self._choreo_task is not None and not self._choreo_task.done()
        for i in (0, 1):
            if self._dirty[i] and not st.decks[i].playing and not busy:
                self.link.reset_deck_fx(i + 1)
                self._dirty[i] = False

    # ---------------------------------------------------------------- biblioteca / fila
    def _refresh_library(self, now: float) -> None:
        if now - self._last_lib < 2.0:
            return
        self._last_lib = now
        self.queue_cache = self.library.autodj_queue(8)
        if now - self._last_count > 30.0:
            self._last_count = now
            self._lib_count = self.library.track_count()

    def _keep_queue(self, now: float) -> None:
        if now - self._last_refill < 10.0:
            return
        if self.library.available and len(self.queue_cache) < MIN_QUEUE:
            self._last_refill = now
            self.link.send("autodj_add_random")
            log.info("Fila do Auto DJ com %d faixa(s): adicionando aleatoria", len(self.queue_cache))

    def _identify_next(self, st: MixxxState, idle_i: int) -> TrackInfo | None:
        """A proxima faixa a tocar ja esta carregada no deck ocioso (o Mixxx a tira da fila)."""
        nd = st.decks[idle_i]
        if nd.loaded and nd.dur > 0:
            t = self.library.find_playing(nd.dur, nd.file_bpm)
            if t:
                return t
        q = self.library.autodj_queue(1)
        return q[0] if q else None

    # ---------------------------------------------------------------- planejamento
    async def _plan(self, key: tuple, cur_i: int) -> None:
        try:
            plan = await self._plan_inner(key, cur_i)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Falha ao planejar transicao - usando padrao do perfil")
            plan = None
        if self._track_key != key:
            return  # a faixa mudou enquanto planejavamos
        st = self.link.state
        d = st.decks[cur_i]
        if plan is None:
            plan = default_plan(self.profile, d.bpm or d.file_bpm, self.cfg.max_overlap_s)
        self.plan = plan
        self._planned = True
        self.link.send("autodj_transition", round(plan.overlap_s))
        log.info(
            "Plano [%s]: blend %d beats (~%.0fs), EQ=%s%s%s",
            plan.source, plan.overlap_beats, plan.overlap_s, plan.eq_style,
            " + filtro" if plan.filter_sweep else "", f" - {plan.note}" if plan.note else "",
        )

    async def _plan_inner(self, key: tuple, cur_i: int) -> TransitionPlan | None:
        idle_i = 1 - cur_i
        plan: TransitionPlan | None = None
        for _ in range(MAX_SKIPS_PER_TRACK + 1):
            if self._track_key != key:
                return None
            st = self.link.state
            d = st.decks[cur_i]
            nxt = self._identify_next(st, idle_i)
            self.next_track = nxt
            score, notes = score_transition(self.cur_track, nxt, self.profile, self.energy) if nxt else (1.0, [])

            if nxt and score < SKIP_THRESHOLD and self._skips < MAX_SKIPS_PER_TRACK and d.remaining > 12:
                log.info("Pulando '%s' (nota %.2f: %s)", nxt.label, score, "; ".join(notes) or "baixa compatibilidade")
                self._skips += 1
                self.link.send("autodj_skip_next")
                await asyncio.sleep(2.0)  # deixa o Mixxx carregar a proxima
                continue

            plan = self.set_planner.find_plan(self.cur_track, nxt, d.bpm or d.file_bpm, self.cfg.max_overlap_s)
            if plan is None and d.remaining > 12:  # sem tempo, nem chama a IA
                plan = await self.agent.plan_transition(
                    profile=self.profile, energy=self.energy, current=self.cur_track,
                    deck_bpm=d.bpm or d.file_bpm, next_track=nxt, heuristic_score=score,
                    heuristic_notes=notes, history=self.history,
                    max_overlap_s=self.cfg.max_overlap_s,
                )
            if plan and not plan.keep_next and nxt and self._skips < MAX_SKIPS_PER_TRACK and d.remaining > 12:
                log.info("IA pediu para pular '%s': %s", nxt.label, plan.note)
                self._skips += 1
                self.link.send("autodj_skip_next")
                await asyncio.sleep(2.0)
                continue
            break

        if plan is not None:
            # nunca deixe o blend maior que o tempo restante da faixa
            st = self.link.state
            d = st.decks[cur_i]
            if d.remaining > 0 and plan.overlap_s > d.remaining - 1.0:
                plan.overlap_s = max(2.0, d.remaining - 1.0)
        return plan

    # ================================================================ status p/ API
    def status(self) -> dict:
        st = self.link.state
        mode = getattr(self.link, "kind", "?")
        return {
            "mode": mode,
            "connected": self.link.connected,
            "port": getattr(self.link, "port_name", None),
            "fresh": self.link.fresh,
            "rx": getattr(self.link, "rx_count", None),
            "autonomous": self.autonomous,
            "allow_downloads": getattr(self, "allow_downloads", False),
            "phase": self.phase,
            "profile": self.profile.public(),
            "profiles": self.store.public_list(),
            "energy": self.energy,
            "mixxx": st.to_dict(),
            "current": self.cur_track.to_dict() if self.cur_track else None,
            "next": self.next_track.to_dict() if self.next_track else None,
            "queue": [t.to_dict() for t in self.queue_cache[:5]],
            "plan": self.plan.to_dict() if self.plan else None,
            "ai": self.agent.info(),
            "history": self.history[-8:],
            "library": {"available": self.library.available, "tracks": getattr(self, "_lib_count", None)},
            "events": list(EVENTS)[-40:],
        }
