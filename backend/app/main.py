import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

from app.api.routes import (
    ac_channels,
    appliances,
    auth,
    batteries,
    clients,
    contact,
    dev,
    events,
    firmware,
    readings,
    reports,
    rs485_sensors,
    sites,
)


@asynccontextmanager
async def lifespan(app_: FastAPI):
    app_.state.sim_tasks: dict[str, asyncio.Task] = {}
    yield
    # Cancel any running simulator tasks on shutdown
    for task in list(app_.state.sim_tasks.values()):
        task.cancel()
    if app_.state.sim_tasks:
        await asyncio.gather(*app_.state.sim_tasks.values(), return_exceptions=True)


app = FastAPI(
    title="batmonai API",
    version="0.1.0",
    description="Multi-tenant battery & inverter monitoring SaaS",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(contact.router)
app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(sites.router)
app.include_router(appliances.router)
app.include_router(batteries.router)
app.include_router(ac_channels.router)
app.include_router(rs485_sensors.router)
app.include_router(readings.router)
app.include_router(events.router)
app.include_router(reports.router)
app.include_router(firmware.router)
app.include_router(dev.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
