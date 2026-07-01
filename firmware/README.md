# batmonai — ESP32 Firmware

PlatformIO project for the ESP32-WROOM-32U gateway.  
Polls PZEM-017 (DC batteries) + PZEM-004T (AC/inverter) + optional RS485
environmental sensors over UART2, then publishes JSON telemetry over MQTT/TLS.

---

## Quick start

```bash
# Install PlatformIO CLI
pip install platformio

# Build
cd firmware
pio run

# Flash (USB connected)
pio run -t upload

# Serial monitor
pio device monitor
```

---

## Configuration — `include/config.h`

Edit **before** flashing.  All provisioning lives here.

| Section | Key constants |
|---------|---------------|
| WiFi | `WIFI_SSID`, `WIFI_PASSWORD` |
| Identity | `APPLIANCE_UID`, `DEVICE_SECRET` (copy from UI after registering the appliance) |
| UIDs | `BATTERY1_UID`, `BATTERY2_UID`, `INVERTER_UID`, `TEMP_HUM_UID`, `GAS_H2_UID` |
| Broker | `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT` |
| TLS | `MQTT_TLS_INSECURE` — set `false` in prod and fill `MQTT_CA_CERT` |
| Slave IDs | Must match server `.env` and DB `modbus_addr` columns |
| Signs | `BATTERY1_CURRENT_SIGN` / `BATTERY2_CURRENT_SIGN` — flip to `-1` if shunt wired reversed |

---

## Wiring

```
ESP32-WROOM-32U               RS485 module
──────────────────            ──────────────
GPIO16 (RX2)  ──────────────► RO
GPIO17 (TX2)  ◄────────────── DI
GPIO4         ──────────────► DE + RE (tied)
3.3 V / 5 V   ──────────────► VCC  (check module voltage)
GND           ──────────────► GND

RS485 A/B bus (daisy-chained)
──────────────────────────────────────────────────────────
A(+) ──── [PZEM-004T addr=1] ── [PZEM-017 addr=2] ── [PZEM-017 addr=3]
B(-) ────  (same daisy chain)
           ── [XY-MD02  addr=4] ── [H2 sensor addr=5]

120 Ω termination resistor at the far end of the bus.
Common GND between all modules and the ESP32.
```

---

## Modbus slave IDs

| Device | Type | Slave ID | Server .env key |
|--------|------|----------|-----------------|
| PZEM-004T (inverter) | AC | 1 | `INVERTER_SLAVE_ID` |
| PZEM-017 (battery 1) | DC | 2 | `BATTERY1_SLAVE_ID` |
| PZEM-017 (battery 2) | DC | 3 | `BATTERY2_SLAVE_ID` |
| XY-MD02 (temp/hum)   | ENV | 4 | `TEMPERATURE_SLAVE_ID` |
| H2 gas sensor        | ENV | 5 | `HYDROGEN_SLAVE_ID` |

Set any `SLAVE_ID_XXX` to `0` in `config.h` to disable that sensor at compile time.

---

## Adding a new RS485 sensor

1. Add `#define SLAVE_ID_NEW_SENSOR N` in `include/config.h` (0 to disable).  
2. Add `#define NEW_SENSOR_UID "..."` in `include/config.h`.  
3. Add a `NewSensorData` struct + `newSensor_read()` function in `include/env_sensors.h` and `src/env_sensors.cpp`.  
4. Add a JSON block in `src/main.cpp` inside `#if SLAVE_ID_NEW_SENSOR != 0`.  
5. Register the sensor in the DB and update server-side `NEWSENSOR_SLAVE_ID` in `.env`.

---

## MQTT topics

| Topic | Direction | Payload |
|-------|-----------|---------|
| `batmon/{appliance_uid}/telemetry` | publish | JSON telemetry |
| `batmon/{appliance_uid}/status`    | publish (LWT) | `online` / `offline` |
| `batmon/{appliance_uid}/cmd`       | subscribe (future) | command JSON |

---

## Store-and-forward

When the broker is unreachable, frames are queued in RAM (FIFO, max
`BUFFER_MAX_FRAMES` = 60 frames ≈ 10 minutes at 10 s interval).  
On reconnect, buffered frames are drained oldest-first before the live frame.
If the buffer fills, the oldest frame is silently dropped.

---

## Production TLS

1. Set `MQTT_TLS_INSECURE false` in `config.h`.
2. Paste the broker's CA certificate (PEM) into `MQTT_CA_CERT`.
3. The broker hostname must match a SAN in the certificate.
