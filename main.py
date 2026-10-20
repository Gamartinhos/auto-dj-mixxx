"""Auto DJ Clone - ponto de entrada.

  .venv\Scripts\python.exe main.py              # Mixxx real (precisa do loopMIDI + mapeamento)
  .venv\Scripts\python.exe main.py --sim        # Mixxx simulado (testa tudo sem o Mixxx)
  .venv\Scripts\python.exe main.py --lan        # expoe na rede local (gera token de acesso)
"""
from __future__ import annotations

import argparse
import logging
from contextlib import asynccontextmanager

import uvicorn

from autodj.ai import DJAgent
from autodj.brain import Brain, RingHandler
from autodj.config import Config
from autodj.library import MixxxLibrary
from autodj.mixxx_link import MidiLink
from autodj.profiles import ProfileStore
from autodj.server import create_app
from autodj.sim import SimLink


def build(cfg: Config) -> tuple[Brain, "object"]:
    store = ProfileStore(cfg.profiles_path)
    agent = DJAgent(cfg)
    if cfg.sim:
        link = SimLink()
        library = link.library
    else:
        link = MidiLink(cfg.midi_port_hint)
        library = MixxxLibrary(cfg.db_path)
    brain = Brain(cfg, link, library, store, agent)

    @asynccontextmanager
    async def lifespan(_app):
        link.start()
        await brain.start()
        try:
            yield
        finally:
            await brain.stop()
            link.close()

    return brain, create_app(brain, cfg, lifespan)


def main() -> None:
    ap = argparse.ArgumentParser(description="Auto DJ Clone para o Mixxx")
    ap.add_argument("--sim", action="store_true", help="usa um Mixxx simulado")
    ap.add_argument("--lan", action="store_true", help="escuta em 0.0.0.0 (celular na mesma rede); exige token")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    ring = RingHandler()
    logging.getLogger("autodj").addHandler(ring)

    cfg = Config()
    cfg.sim = args.sim
    if args.lan:
        cfg.host = "0.0.0.0"  # noqa: S104 - opt-in explicito, protegido por token
    if args.host:
        cfg.host = args.host
    if args.port:
        cfg.port = args.port
    cfg.ensure_token_for_lan()

    _brain, app = build(cfg)

    shown = "localhost" if not cfg.is_lan else "<IP-do-PC>"
    url = f"http://{shown}:{cfg.port}/"
    if cfg.token:
        url += f"?t={cfg.token}"
    logging.getLogger("autodj").info("Interface: %s  (modo: %s)", url, "SIMULADO" if cfg.sim else "Mixxx real")
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="warning")


if __name__ == "__main__":
    main()
