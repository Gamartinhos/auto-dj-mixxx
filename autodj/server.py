"""API FastAPI + interface mobile (web/index.html)."""
from __future__ import annotations

import hmac
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .brain import Brain
from .config import ROOT, Config

log = logging.getLogger("autodj.server")
WEB_DIR = ROOT / "web"


class ProfileBody(BaseModel):
    id: str = Field(min_length=1, max_length=64)


class ToggleBody(BaseModel):
    enabled: bool


class EnergyBody(BaseModel):
    value: int = Field(ge=0, le=100)


class TrickBody(BaseModel):
    trick: str = Field(min_length=1, max_length=64)


def create_app(brain: Brain, cfg: Config, lifespan=None) -> FastAPI:
    app = FastAPI(title="Auto DJ Clone", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)

    def auth(x_token: str | None = Header(default=None), t: str | None = Query(default=None)) -> None:
        if not cfg.token:
            return
        given = x_token or t or ""
        if not hmac.compare_digest(given.encode(), cfg.token.encode()):
            raise HTTPException(status_code=401, detail="token invalido")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True, "mode": brain.link.kind, "connected": brain.link.connected}

    @app.get("/api/status", dependencies=[Depends(auth)])
    async def status() -> JSONResponse:
        return JSONResponse(brain.status())

    @app.get("/api/profiles", dependencies=[Depends(auth)])
    async def profiles() -> dict:
        return {"current": brain.profile.id, "profiles": brain.store.public_list()}

    @app.post("/api/profile", dependencies=[Depends(auth)])
    async def set_profile(body: ProfileBody) -> dict:
        if not await brain.set_profile(body.id):
            raise HTTPException(status_code=404, detail=f"perfil '{body.id}' nao existe")
        return {"ok": True, "profile": brain.profile.public(), "energy": brain.energy}

    @app.post("/api/autonomous", dependencies=[Depends(auth)])
    async def autonomous(body: ToggleBody) -> dict:
        brain.set_autonomous(body.enabled)
        return {"ok": True, "autonomous": brain.autonomous}

    @app.post("/api/allow_downloads", dependencies=[Depends(auth)])
    async def allow_downloads(body: ToggleBody) -> dict:
        brain.set_allow_downloads(body.enabled)
        return {"ok": True, "allow_downloads": brain.allow_downloads}

    @app.post("/api/energy", dependencies=[Depends(auth)])
    async def energy(body: EnergyBody) -> dict:
        brain.set_energy(body.value)
        return {"ok": True, "energy": brain.energy}

    @app.post("/api/mix_now", dependencies=[Depends(auth)])
    async def mix_now() -> dict:
        _require_link(brain)
        brain.mix_now()
        return {"ok": True}

    @app.post("/api/skip_next", dependencies=[Depends(auth)])
    async def skip_next() -> dict:
        _require_link(brain)
        brain.skip_next()
        return {"ok": True}

    @app.post("/api/add_random", dependencies=[Depends(auth)])
    async def add_random() -> dict:
        _require_link(brain)
        brain.add_random()
        return {"ok": True}

    @app.post("/api/mixxx_autodj", dependencies=[Depends(auth)])
    async def mixxx_autodj(body: ToggleBody) -> dict:
        _require_link(brain)
        brain.set_mixxx_autodj(body.enabled)
        return {"ok": True}

    @app.post("/api/trick", dependencies=[Depends(auth)])
    async def trick(body: TrickBody) -> dict:
        _require_link(brain)
        res = await brain.trigger_trick(body.trick)
        return res

    return app


def _require_link(brain: Brain) -> None:
    if not brain.link.connected:
        raise HTTPException(status_code=503, detail="Mixxx desconectado (porta MIDI nao aberta)")
