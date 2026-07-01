"""Pydantic models for the MQTT telemetry payload (§4 of CLAUDE.md)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DcChannelPayload(BaseModel):
    battery_uid: str
    addr: int
    v: float  # voltage (V)
    i: float  # current (A) — negative on discharge, positive on charge
    p: float  # power (W)
    e: float  # energy cumulative total (Wh)
    shunt: int = 100
    alarm: int = 0


class AcChannelPayload(BaseModel):
    channel_uid: str
    addr: int
    v: float
    i: float
    p: float
    e: float
    freq: float = 0.0
    pf: float = 0.0


class EnvSensorPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    sensor_uid: str
    type: str
    addr: int


class TelemetryPayload(BaseModel):
    appliance_uid: str
    ts: datetime
    fw: str | None = None
    dc: list[DcChannelPayload] = Field(default_factory=list)
    ac: list[AcChannelPayload] = Field(default_factory=list)
    env: list[EnvSensorPayload] = Field(default_factory=list)
