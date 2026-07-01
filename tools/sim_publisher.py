#!/usr/bin/env python3
"""
Simulates an ESP32 gateway publishing MQTT telemetry for batmonai.

Publishes to: batmon/{appliance_uid}/telemetry  (QoS 1)
              batmon/{appliance_uid}/status       (LWT = "offline", connect = "online")

Default mode: plain MQTT, no auth (connects to 1883 / host-port 1884).
TLS mode:     pass --tls --ca-cert mosquitto/certs/ca.crt --username uid --password pw

Usage:
    python tools/sim_publisher.py \\
        --appliance-uid test-appliance-001 \\
        --battery-uids  test-battery-001,test-battery-002 \\
        --channel-uids  test-channel-mains \\
        --sensor-uids   test-sensor-sht20 \\
        --broker localhost --port 1884 --interval 10

    # Mains-outage scenario (30 s on, 60 s off, repeat):
    python tools/sim_publisher.py --appliance-uid test-appliance-001 \\
        --battery-uids test-battery-001 --channel-uids test-channel-mains \\
        --broker localhost --port 1884 --interval 5 --outage-cycle 30 60
"""
import argparse
import json
import random
import ssl
import sys
import time
from datetime import datetime, timezone
from typing import Any

try:
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion
except ImportError:
    print("ERROR: paho-mqtt>=2.1.0 is required.  Install with:  pip install 'paho-mqtt>=2.1.0'")
    sys.exit(1)


# ── Simulation state ──────────────────────────────────────────────────────────

class BatteryState:
    NOMINAL_V = 12.0
    FULL_V    = 12.8
    EMPTY_V   = 11.0

    def __init__(self, uid: str, addr: int, shunt_a: int = 100) -> None:
        self.uid       = uid
        self.addr      = addr
        self.shunt_a   = shunt_a
        self.voltage   = self.FULL_V + random.uniform(-0.1, 0.1)
        self.energy_wh = 0.0

    def tick(self, dt_s: float, mains_ok: bool) -> dict[str, Any]:
        if mains_ok:
            target_v = 13.8
            charge_i = max(0.5, (target_v - self.voltage) * 10.0) + random.uniform(-0.2, 0.2)
            self.voltage = min(target_v, self.voltage + 0.005 * dt_s + random.uniform(0, 0.002))
            current = charge_i
        else:
            discharge_i = 10.0 + random.uniform(-0.5, 0.5)
            drop = discharge_i * dt_s * 0.0001
            self.voltage = max(self.EMPTY_V, self.voltage - drop)
            current = -discharge_i

        power = self.voltage * current
        self.energy_wh += abs(power) * dt_s / 3600.0
        alarm = 0x01 if self.voltage <= self.EMPTY_V + 0.2 else 0

        return {
            "battery_uid": self.uid,
            "addr": self.addr,
            "v": round(self.voltage, 3),
            "i": round(current, 2),
            "p": round(power, 1),
            "e": round(self.energy_wh, 2),
            "shunt": self.shunt_a,
            "alarm": alarm,
        }


class AcChannelState:
    def __init__(self, uid: str, addr: int) -> None:
        self.uid       = uid
        self.addr      = addr
        self.energy_wh = 0.0

    def tick(self, dt_s: float, mains_ok: bool) -> dict[str, Any]:
        if mains_ok:
            v    = 230.0 + random.uniform(-3.0, 3.0)
            i    = 4.5   + random.uniform(-0.2, 0.2)
            freq = 50.0  + random.uniform(-0.05, 0.05)
            pf   = 0.95  + random.uniform(-0.02, 0.02)
        else:
            v = i = freq = pf = 0.0

        p = v * i * pf
        self.energy_wh += p * dt_s / 3600.0
        return {
            "channel_uid": self.uid,
            "addr": self.addr,
            "v": round(v, 1),
            "i": round(i, 3),
            "p": round(p, 1),
            "e": round(self.energy_wh, 2),
            "freq": round(freq, 2),
            "pf": round(pf, 3),
        }


class SensorState:
    """Simulates an SHT20 temp/humidity sensor on the RS485 bus."""

    def __init__(self, uid: str, addr: int, sensor_type: str = "temp_humidity") -> None:
        self.uid  = uid
        self.addr = addr
        self.type = sensor_type
        self._t   = 28.0 + random.uniform(-2, 2)
        self._rh  = 55.0 + random.uniform(-5, 5)

    def tick(self, dt_s: float) -> dict[str, Any]:
        self._t  += random.uniform(-0.05, 0.05)
        self._rh += random.uniform(-0.1,  0.1)
        self._t   = max(20.0, min(50.0, self._t))
        self._rh  = max(20.0, min(95.0, self._rh))
        return {
            "sensor_uid": self.uid,
            "type": self.type,
            "addr": self.addr,
            "temperature_c": round(self._t, 2),
            "humidity_pct":  round(self._rh, 1),
        }


# ── Publisher ─────────────────────────────────────────────────────────────────

class SimPublisher:
    def __init__(
        self,
        appliance_uid: str,
        batteries: list[BatteryState],
        channels: list[AcChannelState],
        sensors: list[SensorState],
        broker: str,
        port: int,
        interval_s: float,
        tls: bool,
        ca_cert: str | None,
        username: str | None,
        password: str | None,
        outage_cycle: tuple[float, float] | None,
    ) -> None:
        self.appliance_uid = appliance_uid
        self.batteries     = batteries
        self.channels      = channels
        self.sensors       = sensors
        self.broker        = broker
        self.port          = port
        self.interval_s    = interval_s
        self.outage_cycle  = outage_cycle

        self._telemetry_topic = f"batmon/{appliance_uid}/telemetry"
        self._status_topic    = f"batmon/{appliance_uid}/status"
        self._seq             = 0
        self._outage_timer    = 0.0
        self._mains_ok        = True

        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=f"sim-{appliance_uid}",
        )
        self._client.will_set(
            topic=self._status_topic,
            payload="offline",
            qos=1,
            retain=False,
        )
        if username:
            self._client.username_pw_set(username, password)
        if tls:
            ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_cert)
            self._client.tls_set_context(ctx)

        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties) -> None:
        if not reason_code.is_failure:
            print(f"[MQTT] Connected to {self.broker}:{self.port}")
            client.publish(self._status_topic, "online", qos=1)
        else:
            print(f"[MQTT] Connection refused: {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        print(f"[MQTT] Disconnected: {reason_code}")

    def _mains_state(self, dt_s: float) -> bool:
        if not self.outage_cycle:
            return True
        on_s, off_s = self.outage_cycle
        self._outage_timer += dt_s
        cycle_len = on_s + off_s
        phase = self._outage_timer % cycle_len
        mains = phase < on_s
        if mains != self._mains_ok:
            print(f"[SIM]  Mains {'RESTORED' if mains else 'FAILED'}")
            self._mains_ok = mains
        return mains

    def run(self) -> None:
        print(f"[SIM]  appliance={self.appliance_uid}  interval={self.interval_s}s")
        print(f"[SIM]  batteries={[b.uid for b in self.batteries]}")
        print(f"[SIM]  channels={[c.uid for c in self.channels]}")
        if self.sensors:
            print(f"[SIM]  sensors={[s.uid for s in self.sensors]}")
        if self.outage_cycle:
            print(f"[SIM]  outage-cycle: {self.outage_cycle[0]}s on / {self.outage_cycle[1]}s off")
        print(f"[SIM]  Connecting to {self.broker}:{self.port}...")

        self._client.connect(self.broker, self.port, keepalive=60)
        self._client.loop_start()

        try:
            last_tick = time.monotonic()
            while True:
                time.sleep(self.interval_s)
                now = time.monotonic()
                dt  = now - last_tick
                last_tick = now

                mains = self._mains_state(dt)
                ts    = datetime.now(timezone.utc).isoformat()

                payload: dict[str, Any] = {
                    "appliance_uid": self.appliance_uid,
                    "ts":            ts,
                    "fw":            "0.1.0-sim",
                    "dc":            [b.tick(dt, mains) for b in self.batteries],
                    "ac":            [c.tick(dt, mains) for c in self.channels],
                    "env":           [s.tick(dt) for s in self.sensors],
                }
                self._seq += 1

                raw = json.dumps(payload)
                result = self._client.publish(self._telemetry_topic, raw, qos=1)
                result.wait_for_publish(timeout=5.0)

                batt_v = payload["dc"][0]["v"] if payload["dc"] else "—"
                print(
                    f"[{self._seq:04d}] ts={ts[-15:-6]}  mains={'OK' if mains else 'OFF'}"
                    f"  batt_v={batt_v}"
                )

        except KeyboardInterrupt:
            print("\n[SIM]  Stopped by user. Publishing graceful offline...")
            self._client.publish(self._status_topic, "offline", qos=1)
            time.sleep(0.5)
        finally:
            self._client.loop_stop()
            self._client.disconnect()
            print("[SIM]  Disconnected.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_uids(raw: str) -> list[str]:
    return [u.strip() for u in raw.split(",") if u.strip()]


def main() -> None:
    p = argparse.ArgumentParser(description="batmonai MQTT telemetry simulator")
    p.add_argument("--appliance-uid", required=True, help="appliance_uid to publish as")
    p.add_argument("--battery-uids",  default="test-battery-001",
                   help="Comma-separated battery_uids (order = modbus addr 1,2,...)")
    p.add_argument("--channel-uids",  default="test-channel-mains",
                   help="Comma-separated AC channel_uids")
    p.add_argument("--sensor-uids",   default="",
                   help="Comma-separated RS485 sensor_uids (blank = no env sensors)")
    p.add_argument("--broker",   default="localhost", help="MQTT broker hostname")
    p.add_argument("--port",     type=int, default=1884, help="MQTT broker port")
    p.add_argument("--interval", type=float, default=10.0, help="Publish interval (seconds)")
    p.add_argument("--tls",      action="store_true", help="Enable TLS")
    p.add_argument("--ca-cert",  default=None, help="CA cert path for TLS")
    p.add_argument("--username", default=None, help="MQTT username")
    p.add_argument("--password", default=None, help="MQTT password")
    p.add_argument("--outage-cycle", nargs=2, type=float, metavar=("ON_S", "OFF_S"),
                   default=None,
                   help="Mains outage cycle: ON_S seconds mains-on, OFF_S seconds mains-off")
    args = p.parse_args()

    batteries = [BatteryState(uid=u, addr=i + 1) for i, u in enumerate(_parse_uids(args.battery_uids))]
    channels  = [AcChannelState(uid=u, addr=i + 1) for i, u in enumerate(_parse_uids(args.channel_uids))]
    sensors   = [SensorState(uid=u, addr=i + 1) for i, u in enumerate(_parse_uids(args.sensor_uids))]
    outage    = tuple(args.outage_cycle) if args.outage_cycle else None  # type: ignore[assignment]

    SimPublisher(
        appliance_uid=args.appliance_uid,
        batteries=batteries,
        channels=channels,
        sensors=sensors,
        broker=args.broker,
        port=args.port,
        interval_s=args.interval,
        tls=args.tls,
        ca_cert=args.ca_cert,
        username=args.username,
        password=args.password,
        outage_cycle=outage,
    ).run()


if __name__ == "__main__":
    main()
