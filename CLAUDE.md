# batmonai — Claude Code Project Brief & Constitution

> Paste this as the kickoff message in Claude Code (VS Code extension), and also commit it as `CLAUDE.md` at the repo root. Treat every rule in §2 as a hard invariant. Build strictly phase-by-phase (§9): do not start a phase until the previous phase's acceptance criteria pass.

---

## 0. Mission

Build **batmonai**, a multi-tenant, Docker-based SaaS for 24/7 monitoring of lead-acid batteries and inverters, reusing the proven architecture of the existing **energyMon** project. Telemetry originates from ESP32 gateways polling PZEM meters over RS485/Modbus-RTU, is published over MQTT/TLS, ingested into TimescaleDB, and surfaced through a React frontend with reporting and event detection.

Dev runs entirely on a laptop via Docker Compose. Prod runs on a Rocky Linux VM (VM4) behind a public IP; domain `batmon.energymonai.com` is fronted by a Caddy on `192.168.0.204` that routes HTTP(S) to VM4. Workflow: develop on laptop → `git push` to `https://github.com/atulrasto/batmonai` → `git pull` on VM4 → `docker compose up -d --build`.

## 1. Stack (do not substitute without asking)

- **Backend/API:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2.
- **DB:** TimescaleDB (Postgres 16). Connection pooling via **PgBouncer** (transaction mode).
- **Migrations:** **Alembic only.**
- **Broker:** Eclipse **Mosquitto** with TLS on 8883 + per-device ACLs.
- **Ingestion:** standalone async Python service (paho-mqtt or asyncio-mqtt) → DB.
- **Frontend:** React + Vite + TypeScript, served by nginx (or Caddy) container.
- **Reverse proxy / TLS:** Caddy (internal to VM4).
- **Firmware:** PlatformIO, ESP32-WROOM-32U, Arduino framework, ModbusMaster.
- **Orchestration:** a single `docker-compose.yml` (+ `docker-compose.prod.yml` override for certs/Caddy). One `.env` drives all config.

## 2. Hard invariants — NEVER violate

1. **Alembic-only schema.** NEVER call `Base.metadata.create_all()`. All DDL — including hypertable creation, continuous aggregates, and RLS policies — lives in Alembic migrations. Migrations must be idempotent and reversible where feasible.
2. **Readings are append-only.** No UPDATE/DELETE on `dc_readings` / `ac_readings`. Corrections are new rows.
3. **Device timestamps are authoritative.** Store the device-reported `ts`; also store `ingested_at = now()`. Never overwrite device time with server time.
4. **Row-Level Security with denormalized `client_id`.** Every tenant-scoped table (including reading hypertables) carries `client_id`. RLS policies isolate tenants; the API sets the tenant context per request. No cross-tenant reads, ever.
5. **No secrets in code or git.** Everything sensitive is in `.env` (git-ignored). Provide `.env.example` with placeholders.
6. **Superuser is seeded from `.env`**, not hardcoded, not migrated as data.
7. **TLS everywhere off-LAN:** API over HTTPS, MQTT over 8883. Dev may use a local CA / self-signed; prod uses real certs.
8. **Single source of truth for the domain hierarchy** (§3). Unique IDs are globally unique strings, human-readable (`client1-site2-appliance1-bat1`).

If a request conflicts with these, stop and flag it rather than silently violating.

## 3. Domain model

Hierarchy: **Client (tenant) → Site → Appliance (ESP32 gateway) → Battery (PZEM-017)** and **Appliance → AC Channel (PZEM-004T)** and optionally **Appliance → RS485 Sensor** (§3a).

Reference tables:

- `users` — `id`, `email`, `password_hash`, `role` (`superuser` | `client`), `client_id` (null for superuser), `must_change_password` (bool, default true), `is_active`, timestamps.
- `clients` — `id`, `name`, `primary_email`, `is_active`, timestamps. One client = one tenant.
- `sites` — `id`, `client_id` (FK), `name`, `slug` (e.g. `site2`), `location`, timestamps.
- `appliances` — `id`, `client_id`, `site_id`, `appliance_uid` (globally unique, e.g. `client1-site2-appliance1`), `name`, `device_secret_hash` (for MQTT auth), `fw_version`, `last_seen_at`, `is_active`.
- `batteries` — `id`, `client_id`, `appliance_id`, `battery_uid` (e.g. `...-bat1`), `modbus_addr` (unique per appliance bus), `shunt_rating_a` (e.g. 100/200/300), `capacity_ah`, `chemistry` (default flooded lead-acid), `nominal_v`.
- `ac_channels` — `id`, `client_id`, `appliance_id`, `channel_uid` (e.g. `...-inv1`), `modbus_addr`, `role` (`inverter_input` | `inverter_output` | `load`).

Hypertables (TimescaleDB):

- `dc_readings` — `time` (device ts), `battery_id`, `client_id`, `voltage`, `current`, `power`, `energy_wh`, `alarm_flags` (int), `ingested_at`. Partition by `time`; index on `(battery_id, time DESC)`.
- `ac_readings` — `time`, `ac_channel_id`, `client_id`, `voltage`, `current`, `power`, `energy_wh`, `frequency`, `power_factor`, `ingested_at`.

Events:

- `events` — `id`, `client_id`, `appliance_id`, `kind` (`discharge_start`, `discharge_end`, `mains_outage`, `low_voltage`, `high_voltage`, `device_offline`, …), `severity`, `detail` (jsonb), `started_at`, `resolved_at`.

Continuous aggregates: hourly + daily rollups per battery (min/max/avg voltage & current, energy delta) and per ac_channel (energy delta, avg load). Used by the reporting layer; never query raw hypertables for long ranges.

## 3a. Optional RS485 sensors (same bus, same appliance)

Any Modbus-RTU sensor sharing the appliance RS485 bus can be registered as an `rs485_sensor`. Each sensor has a `sensor_type` that determines which reading fields are populated. Firmware polls these at the same cadence as PZEM meters.

**Currently supported sensor types:**

| `sensor_type`   | Module example | Registers / payload fields |
|-----------------|---------------|---------------------------|
| `temp_humidity` | XY-MD02 (SHT20) | `temperature_c`, `humidity_pct` |
| `gas_h2`        | Generic H₂ detector | `ppm`, `alarm` (bool) |

Table: `rs485_sensors` — `id`, `client_id`, `appliance_id`, `sensor_uid` (e.g. `client1-site2-appliance1-env1`), `sensor_type`, `modbus_addr`, `name`, `is_active`.

Hypertable: `sensor_readings` — `time`, `sensor_id`, `client_id`, `payload` (JSONB — keys vary by `sensor_type`), `ingested_at`. Index on `(sensor_id, time DESC)`.

**Design rules:**
- All sensor tables carry `client_id` (RLS applies).
- `sensor_uid` globally unique, human-readable, follows the same hierarchy convention.
- Sensor presence is **optional** per appliance — zero sensors is valid.
- New sensor types are added by inserting a new `sensor_type` enum value and updating firmware polling logic; no schema migration needed (JSONB payload is flexible).
- Thresholds (e.g. H₂ alarm ppm) are stored in `rs485_sensors.config` (JSONB) and evaluated by the rules engine (§5).

**MQTT payload extension** — the telemetry JSON gains an optional `env` array alongside `dc` and `ac`:

```json
"env": [
  { "sensor_uid": "...-env1", "type": "temp_humidity", "addr": 5, "temperature_c": 34.2, "humidity_pct": 61.5 },
  { "sensor_uid": "...-gas1", "type": "gas_h2",         "addr": 6, "ppm": 12, "alarm": false }
]
```

## 4. Telemetry & MQTT contract

**Topics**

- Publish: `batmon/{appliance_uid}/telemetry`
- Commands (future): `batmon/{appliance_uid}/cmd`
- Status (LWT): `batmon/{appliance_uid}/status` → `online` / `offline`

**Auth:** each appliance authenticates with username = `appliance_uid`, password = device secret (or client cert). Mosquitto ACL: an appliance may only publish to its own `batmon/{appliance_uid}/#`.

**Payload (JSON, published every N seconds, default 10s):**

```json
{
  "appliance_uid": "client1-site2-appliance1",
  "ts": "2026-06-30T10:00:00Z",
  "fw": "1.0.0",
  "dc": [
    { "battery_uid": "client1-site2-appliance1-bat1", "addr": 1, "v": 12.84, "i": -5.20, "p": 66.8, "e": 1234.5, "shunt": 100, "alarm": 0 },
    { "battery_uid": "client1-site2-appliance1-bat2", "addr": 2, "v": 12.81, "i": -5.10, "p": 65.3, "e": 1100.2, "shunt": 100, "alarm": 0 }
  ],
  "ac": [
    { "channel_uid": "client1-site2-appliance1-inv1", "addr": 10, "v": 0.0, "i": 0.0, "p": 0.0, "e": 540.1, "freq": 0.0, "pf": 0.0 }
  ]
}
```

**Sign convention:** DC `i` is **negative on discharge** (current leaving the battery), positive on charge — fixed by shunt orientation. PZEM-017 reports magnitude; encode direction in firmware from shunt wiring. Energy fields are cumulative meter totals; the ingestion layer computes deltas.

**Ingestion service:** subscribe to `batmon/+/telemetry`, validate against a Pydantic schema, resolve `appliance_uid` → ids (cache with TTL), reject unknown/unauthorized appliances, insert into hypertables in batches, update `appliances.last_seen_at`, and emit `device_offline` events on LWT.

## 5. Event / rules engine

Two-tier, stateless rules first; keep room for an ML tier later.

Core rules (evaluate per appliance per ingest window):

- **Inverter discharging / mains outage:** `ac.inverter_input.v ≈ 0` **AND** any battery `i` indicates discharge beyond threshold → open `mains_outage` + `discharge_start`; close when AC voltage returns and current goes non-discharge.
- **Charging / float:** AC present and battery current positive → `charging`; tapering near nominal voltage → `float`.
- **Low/High voltage:** per-battery thresholds (configurable, defaults sane for 12V flooded lead-acid) → `low_voltage` / `high_voltage`.
- **Device offline:** no telemetry for > 3× publish interval → `device_offline`.
- **High temperature / humidity (optional):** if a `temp_humidity` sensor is present and reading exceeds configurable thresholds → `high_temperature` / `high_humidity` events.
- **H₂ gas alarm (optional):** if a `gas_h2` sensor reports `alarm=true` or `ppm` exceeds threshold → `h2_gas_alarm` event (high severity; triggers immediate notification).

Events drive notifications (email/webhook, reuse energyMon) and reports.

## 6. Services & docker-compose

One base `docker-compose.yml`. Services:

1. `postgres` — TimescaleDB image, named volume, healthcheck.
2. `pgbouncer` — transaction pooling in front of postgres; API + ingestion connect through it.
3. `mosquitto` — config + TLS certs + ACL/password files mounted; ports 8883 (+ 1883 LAN-only in dev).
4. `migrate` — one-shot: runs `alembic upgrade head`, then exits. API/ingestion `depends_on` it completing.
5. `api` — FastAPI (uvicorn), depends on `migrate` + `pgbouncer`.
6. `ingestion` — depends on `migrate` + `pgbouncer` + `mosquitto`.
7. `frontend` — built React static served by nginx/Caddy.
8. `caddy` — internal reverse proxy/TLS (prod override wires real certs + the `batmon.energymonai.com` vhost).

Requirements: every service has a healthcheck; use `depends_on: condition: service_healthy` / `service_completed_successfully`; named volumes for pg data, mosquitto data, caddy data; a single `.env` consumed via `env_file`. `make up`, `make down`, `make logs`, `make migrate`, `make seed` targets.

## 7. Auth & multi-tenancy

- Superuser seeded on first boot from `SUPERUSER_EMAIL` / `SUPERUSER_PASSWORD` with `must_change_password=true`.
- Login → if `must_change_password`, force a change-password step before any other action; clear the flag on success.
- Superuser creates clients; on creation the system generates a temp password and emails the client (SMTP from `.env`), `must_change_password=true`.
- Client logs in → forced change → then manages own sites, appliances, batteries, ac_channels.
- All tenant queries run under RLS bound to the authenticated user's `client_id`. Superuser may impersonate/scope explicitly but never leaks cross-tenant data by default.

## 8. Dev vs Prod

**Dev (laptop):** local CA / self-signed certs for HTTPS + MQTT TLS (mkcert is fine); `1883` exposed on LAN for quick firmware testing; hot-reload for API and frontend; seed data optional.

**Prod (VM4, Rocky Linux):** `docker-compose.prod.yml` override adds the `batmon.energymonai.com` Caddy vhost and real certs. The **front Caddy on `192.168.0.204` reverse-proxies HTTP(S) only**. MQTT/TLS on **8883 is raw TCP** — provide an L4 forward (caddy-l4 plugin **or** firewalld/iptables DNAT on the front VM **or** a direct public-IP port-forward) to VM4:8883. Document this in `docs/deploy.md`. Deploy runbook: `git pull` → `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` (migrations run via the `migrate` service).

## 9. Build phases (strict order; gate on acceptance)

**Phase 0 — Scaffold.** Repo layout (§10), `CLAUDE.md`, base `docker-compose.yml` skeleton, `.env.example`, `.gitignore`, ruff/black, pre-commit, `Makefile`.
*Accept:* `docker compose config` validates; repo lints clean.

**Phase 1 — Data layer.** TimescaleDB + PgBouncer up. Models + Alembic migrations for all reference tables, hypertables, RLS policies, continuous aggregates. Superuser seed command.
*Accept:* `alembic upgrade head` builds the full schema from empty; `\d` shows hypertables + RLS; seed creates superuser; downgrade path documented.

**Phase 2 — API + auth.** FastAPI, JWT, forced-password-change flow, tenant CRUD with RLS.
*Accept:* superuser first-login forces change; can create a client; client first-login forces change; cross-tenant access denied (test proves it).

**Phase 3 — MQTT + ingestion.** Mosquitto TLS + ACLs; ingestion validates and writes; unknown appliance rejected; `last_seen_at` updates.
*Accept:* a simulated publisher (`tools/sim_publisher.py`) drives rows into `dc_readings`/`ac_readings`; bad payloads rejected; offline LWT raises `device_offline`.

**Phase 4 — Firmware.** PlatformIO project: ModbusMaster over `HardwareSerial(2)` (GPIO16 RX2 / GPIO17 TX2), poll N×PZEM-017 + 1×PZEM-004T at distinct addresses, store-and-forward buffer, MQTT/TLS publish, provisioning (`appliance_uid`, broker, creds, WiFi).
*Accept:* against real or simulated bus, publishes valid payloads; survives broker disconnects via buffer; addresses configurable.

**Phase 5 — Rules/events.** Implement §5 detectors; persist events; wire notifications.
*Accept:* AC-zero + discharge current produces `mains_outage`+`discharge_start` and resolves correctly; thresholds configurable.

**Phase 6 — Frontend.** Login + forced change; client/site/appliance/battery tree; live + historical charts; inverter view; basic admin (superuser→clients, client→sites/appliances/batteries).
*Accept:* full create-down-the-hierarchy flow in the UI; charts read aggregates, not raw, for long ranges.

**Phase 7 — Reporting.** Aggregate-backed reports, PDF export, email/webhook alerts.
*Accept:* daily per-battery + per-inverter PDF generates; alert fires on a simulated event.

**Phase 8 — Prod.** `docker-compose.prod.yml`, VM4 Caddy + certs, L4 8883 forward, backups, healthchecks, `docs/deploy.md`.
*Accept:* documented end-to-end deploy on VM4; device on the internet publishes through to DB; HTTPS site live on `batmon.energymonai.com`.

## 10. Repo layout

```
batmonai/
  CLAUDE.md
  docker-compose.yml
  docker-compose.prod.yml
  .env.example
  Makefile
  backend/            # FastAPI app
    app/ (api, core, models, schemas, services, auth, rls)
    alembic/ (env.py, versions/)
  ingestion/          # MQTT → DB service
  frontend/           # React + Vite + TS
  firmware/           # PlatformIO ESP32 project
  mosquitto/          # mosquitto.conf, acl, certs/ (gitignored)
  caddy/              # Caddyfile(s)
  tools/              # sim_publisher.py, seed scripts
  docs/               # deploy.md, wiring.md, mqtt.md
```

## 11. Hardware reference (firmware phase — verify against Wiring.JPG before flashing)

- **ESP32-WROOM-32U UART2:** GPIO16 = RX2, GPIO17 = TX2. RS485 module: `RO`→GPIO16, `DI`→GPIO17, `DE`+`RE` tied to a GPIO (e.g. GPIO4) unless auto-direction; module VCC/GND per its logic level.
- **Bus:** A/B daisy-chained to every PZEM-017 and the PZEM-004T; 120 Ω termination at both ends; common ground reference.
- **Addressing:** each meter set to a unique Modbus slave address (PZEM default is broadcast `0xF8`; assign 1,2,3,… before deployment). Store the mapping in `batteries.modbus_addr` / `ac_channels.modbus_addr`.
- **PZEM-017 (DC) input registers:** `0x0000` voltage, `0x0001` current, `0x0002–3` power, `0x0004–5` energy, `0x0006` high-volt alarm, `0x0007` low-volt alarm. Holding regs configure thresholds, slave address (`0x0002`), and shunt rating (`0x0003`: 100/50/200/300 A). Serial 9600 baud — confirm parity/stop bits against the datasheet.
- **PZEM-004T (AC):** voltage, current, power, energy, frequency, power factor over the same bus at its own address; route via the appliance like the DC meters. Confirm whether the unit is the RS485 variant or needs a TTL→RS485 bridge.
- **Current sign:** wire/encode so discharge = negative DC current (see §4).

## 12. First task for Claude Code

Start **Phase 0** only. Create the repo skeleton in §10, a validating `docker-compose.yml` skeleton (service names + healthcheck stubs, no business logic), `.env.example` covering DB/PgBouncer/Mosquitto/SMTP/superuser/JWT, `.gitignore` (certs, `.env`, `__pycache__`, `node_modules`, build artifacts), ruff+black config, pre-commit, and a `Makefile` with `up/down/logs/migrate/seed`. Print the resulting tree and the Phase 0 acceptance check, then **stop and wait** before Phase 1.
