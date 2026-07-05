"""Simulator control routes — start/stop/tune the live data feed, read its status.

The engine lives on app.state.sim (built in the lifespan). Config changes apply live.
"""
from fastapi import APIRouter, Request

from backend.schemas import SimConfigReq

router = APIRouter(prefix="/sim", tags=["simulator"])


def _sim(request: Request):
    return request.app.state.sim


@router.get("/status")
async def status(request: Request):
    return _sim(request).status()


@router.post("/start")
async def start(body: SimConfigReq, request: Request):
    sim = _sim(request)
    await sim.start(body.model_dump(exclude_none=True))
    return sim.status()


@router.post("/stop")
async def stop(request: Request):
    sim = _sim(request)
    await sim.stop()
    return sim.status()


@router.post("/config")
async def config(body: SimConfigReq, request: Request):
    """Update knobs live (speed, rates, toggles) without stopping the run."""
    sim = _sim(request)
    await sim.update(body.model_dump(exclude_none=True))
    return sim.status()
